// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title HotelBooking
/// @notice Simple escrow for hotel bookings without middlemen.
/// @dev Dates here are "day numbers" (timestamp / 1 day). Use the today() function in Remix to test.
contract HotelBooking {

    enum Status { None, Booked, CheckedIn, Cancelled, Rejected, NoShow }

    struct Room {
        uint256 id;
        address hotel;
        string description;
        uint256 pricePerNight; // in wei
        bool active;
    }

    struct Booking {
        uint256 id;
        uint256 roomId;
        address guest;
        address hotel;
        uint32 checkInDay;
        uint32 checkOutDay;
        uint256 amountPaid;
        bytes32 guestDataHash; // hash of guest details (kept off-chain for privacy)
        Status status;
    }

    // app cancellation rules
    uint32 public constant FREE_CANCELLATION_DAYS = 2; // 48h before check-in
    uint256 public constant LATE_CANCEL_FEE_PERCENT = 50;
    uint32 public constant MAX_NIGHTS = 30;

    mapping(address => string) public hotelNames;
    mapping(uint256 => Room) private rooms;
    mapping(uint256 => Booking) private bookings;
    // roomId => day number => if it's taken (prevents double booking)
    mapping(uint256 => mapping(uint32 => bool)) public nightTaken;
    mapping(address => uint256) public pendingWithdrawals;
    mapping(address => uint256[]) private bookingsOfGuest;
    mapping(address => uint256[]) private roomsOfHotel;

    uint256 public roomCount;
    uint256 public bookingCount;

    bool private locked;

    event HotelRegistered(address indexed hotel, string name);
    event RoomAdded(uint256 indexed roomId, address indexed hotel, uint256 pricePerNight);
    event RoomStatusChanged(uint256 indexed roomId, bool active);
    event RoomBooked(uint256 indexed bookingId, uint256 indexed roomId, address indexed guest,
                     uint32 checkInDay, uint32 checkOutDay, uint256 amount);
    event BookingCancelled(uint256 indexed bookingId, uint256 refundToGuest, uint256 feeToHotel);
    event BookingRejected(uint256 indexed bookingId, uint256 refundToGuest);
    event GuestCheckedIn(uint256 indexed bookingId, address indexed guest, uint256 paidToHotel);
    event NoShowRecorded(uint256 indexed bookingId, uint256 paidToHotel);
    event Withdrawal(address indexed account, uint256 amount);

    modifier onlyRegisteredHotel() {
        require(bytes(hotelNames[msg.sender]).length > 0, "Not a registered hotel");
        _;
    }

    modifier noReentrancy() {
        require(!locked, "Reentrant call");
        locked = true;
        _;
        locked = false;
    }

    // ------------------------------------------------------------------
    // Hotel side
    // ------------------------------------------------------------------

    function registerHotel(string calldata name) external {
        require(bytes(name).length > 0, "Name required");
        require(bytes(hotelNames[msg.sender]).length == 0, "Hotel already registered");
        hotelNames[msg.sender] = name;
        emit HotelRegistered(msg.sender, name);
    }

    function addRoom(string calldata description, uint256 pricePerNight)
        external onlyRegisteredHotel returns (uint256)
    {
        require(pricePerNight > 0, "Price must be > 0");
        roomCount++;
        rooms[roomCount] = Room(roomCount, msg.sender, description, pricePerNight, true);
        roomsOfHotel[msg.sender].push(roomCount);
        emit RoomAdded(roomCount, msg.sender, pricePerNight);
        return roomCount;
    }

    function setRoomActive(uint256 roomId, bool active) external {
        require(rooms[roomId].hotel == msg.sender, "Not your room");
        rooms[roomId].active = active;
        emit RoomStatusChanged(roomId, active);
    }

    /// @notice If something goes wrong (overbooking, maintenance), the hotel rejects and gives a full refund.
    function rejectBooking(uint256 bookingId) external {
        Booking storage b = bookings[bookingId];
        require(b.hotel == msg.sender, "Not your booking");
        require(b.status == Status.Booked, "Booking not active");

        b.status = Status.Rejected;
        _releaseNights(b.roomId, b.checkInDay, b.checkOutDay);
        pendingWithdrawals[b.guest] += b.amountPaid;
        emit BookingRejected(bookingId, b.amountPaid);
    }

    /// @notice Check-in via guest's ECDSA signature proving they arrived at the desk.
    function checkIn(uint256 bookingId, bytes calldata guestSignature) external {
        Booking storage b = bookings[bookingId];
        require(b.hotel == msg.sender, "Not your booking");
        require(b.status == Status.Booked, "Booking not active");
        uint32 t = today();
        require(t >= b.checkInDay && t < b.checkOutDay, "Outside the stay dates");

        bytes32 ethHash = toEthSignedMessageHash(getCheckInMessageHash(bookingId));
        require(recoverSigner(ethHash, guestSignature) == b.guest, "Invalid guest signature");

        b.status = Status.CheckedIn;
        pendingWithdrawals[b.hotel] += b.amountPaid;
        emit GuestCheckedIn(bookingId, b.guest, b.amountPaid);
    }

    /// @notice If the guy doesn't show up after the check-in day, the hotel takes the cash.
    function markNoShow(uint256 bookingId) external {
        Booking storage b = bookings[bookingId];
        require(b.hotel == msg.sender, "Not your booking");
        require(b.status == Status.Booked, "Booking not active");
        require(today() > b.checkInDay, "Check-in day not finished");

        b.status = Status.NoShow;
        _releaseNights(b.roomId, today(), b.checkOutDay);
        pendingWithdrawals[b.hotel] += b.amountPaid;
        emit NoShowRecorded(bookingId, b.amountPaid);
    }

    // ------------------------------------------------------------------
    // Guest side
    // ------------------------------------------------------------------

    function bookRoom(uint256 roomId, uint32 checkInDay, uint32 checkOutDay, bytes32 guestDataHash)
        external payable returns (uint256)
    {
        Room storage r = rooms[roomId];
        require(r.active, "Room not available");
        require(msg.sender != r.hotel, "Hotel cannot book own room");
        require(checkInDay >= today(), "Check-in in the past");
        require(checkOutDay > checkInDay, "Check-out must be after check-in");
        require(checkOutDay - checkInDay <= MAX_NIGHTS, "Too many nights");
        require(isAvailable(roomId, checkInDay, checkOutDay), "Room already booked for these dates");

        uint256 price = r.pricePerNight * (checkOutDay - checkInDay);
        require(msg.value == price, "Send the exact price (use quotePrice)");

        for (uint32 d = checkInDay; d < checkOutDay; d++) {
            nightTaken[roomId][d] = true;
        }

        bookingCount++;
        bookings[bookingCount] = Booking(bookingCount, roomId, msg.sender, r.hotel,
            checkInDay, checkOutDay, msg.value, guestDataHash, Status.Booked);
        bookingsOfGuest[msg.sender].push(bookingCount);

        emit RoomBooked(bookingCount, roomId, msg.sender, checkInDay, checkOutDay, msg.value);
        return bookingCount;
    }

    /// @notice Cancels the booking. Up to 48h before is free, after that there's a 50% fee.
    function cancelBooking(uint256 bookingId) external {
        Booking storage b = bookings[bookingId];
        require(b.guest == msg.sender, "Not your booking");
        require(b.status == Status.Booked, "Booking not active");
        uint32 t = today();
        require(t <= b.checkInDay, "Too late to cancel");

        uint256 fee = 0;
        if (t + FREE_CANCELLATION_DAYS > b.checkInDay) {
            fee = (b.amountPaid * LATE_CANCEL_FEE_PERCENT) / 100;
        }
        uint256 refund = b.amountPaid - fee;

        b.status = Status.Cancelled;
        _releaseNights(b.roomId, b.checkInDay, b.checkOutDay);
        pendingWithdrawals[b.guest] += refund;
        pendingWithdrawals[b.hotel] += fee;
        emit BookingCancelled(bookingId, refund, fee);
    }

    // ------------------------------------------------------------------
    // Payments (Pull pattern: everyone withdraws their own)
    // ------------------------------------------------------------------

    function withdraw() external noReentrancy {
        uint256 amount = pendingWithdrawals[msg.sender];
        require(amount > 0, "Nothing to withdraw");
        pendingWithdrawals[msg.sender] = 0; // zero out before sending to prevent reentrancy
        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        require(ok, "Transfer failed");
        emit Withdrawal(msg.sender, amount);
    }

    // ------------------------------------------------------------------
    // View Functions (Useful Getters)
    // ------------------------------------------------------------------

    function today() public view returns (uint32) {
        return uint32(block.timestamp / 1 days);
    }

    function isAvailable(uint256 roomId, uint32 checkInDay, uint32 checkOutDay) public view returns (bool) {
        if (!rooms[roomId].active || checkOutDay <= checkInDay) return false;
        for (uint32 d = checkInDay; d < checkOutDay; d++) {
            if (nightTaken[roomId][d]) return false;
        }
        return true;
    }

    function quotePrice(uint256 roomId, uint32 checkInDay, uint32 checkOutDay) external view returns (uint256) {
        require(checkOutDay > checkInDay, "Invalid dates");
        return rooms[roomId].pricePerNight * (checkOutDay - checkInDay);
    }

    function getRoom(uint256 roomId) external view returns (Room memory) {
        return rooms[roomId];
    }

    function getBooking(uint256 bookingId) external view returns (Booking memory) {
        return bookings[bookingId];
    }

    function getGuestBookings(address guest) external view returns (uint256[] memory) {
        return bookingsOfGuest[guest];
    }

    function getHotelRooms(address hotel) external view returns (uint256[] memory) {
        return roomsOfHotel[hotel];
    }

    function escrowBalance() external view returns (uint256) {
        return address(this).balance;
    }

    // ------------------------------------------------------------------
    // Cryptography / Signatures (Keccak-256 + ECDSA)
    // ------------------------------------------------------------------

    /// @notice Hash of the message the guest signs at check-in.
    /// @dev Included contract address and chainId to avoid replay attacks on other networks/contracts.
    function getCheckInMessageHash(uint256 bookingId) public view returns (bytes32) {
        return keccak256(abi.encodePacked(address(this), block.chainid, bookingId, "CHECK-IN"));
    }

    /// @dev Standard prefix to match wallet personal_sign.
    function toEthSignedMessageHash(bytes32 hash) public pure returns (bytes32) {
        return keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", hash));
    }

    function recoverSigner(bytes32 ethSignedHash, bytes memory sig) public pure returns (address) {
        require(sig.length == 65, "Signature must be 65 bytes");
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := mload(add(sig, 32))
            s := mload(add(sig, 64))
            v := byte(0, mload(add(sig, 96)))
        }
        if (v < 27) v += 27;
        require(v == 27 || v == 28, "Bad signature v");
        // prevents signature malleability by rejecting "high s"
        require(uint256(s) <= 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0, "Bad signature s");
        address signer = ecrecover(ethSignedHash, v, r, s);
        require(signer != address(0), "Invalid signature");
        return signer;
    }

    function _releaseNights(uint256 roomId, uint32 fromDay, uint32 toDay) private {
        for (uint32 d = fromDay; d < toDay; d++) {
            nightTaken[roomId][d] = false;
        }
    }
}