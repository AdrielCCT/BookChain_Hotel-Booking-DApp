"""Full demo of the booking flow between a guest (sender) and a hotel (receiver)
with the HotelBooking contract in the middle holding the money.

Run this on a fresh Ganache instance (the last part moves the chain clock forward).
"""
from web3.exceptions import ContractLogicError

from common import (GUEST, GUEST_2, HOTEL, connect, eth, guest_data_hash, load_deployed,
                    send, sign_check_in, time_travel)

STATUS = ["None", "Booked", "CheckedIn", "Cancelled", "Rejected", "NoShow"]


def title(text):
    print("\n" + "=" * 70 + f"\n{text}\n" + "=" * 70)


def show_booking(c, booking_id):
    b = c.functions.getBooking(booking_id).call()
    print(f"  Booking #{b[0]} | room {b[1]} | guest {b[2][:10]}... | days {b[4]}->{b[5]} "
          f"| paid {b[6]} wei | status {STATUS[b[8]]}")


def expect_revert(label, fn, sender, value=0):
    try:
        fn.transact({"from": sender, "value": value})
        print(f"  [!] {label}: this should have failed")
    except ContractLogicError as e:
        print(f"  [OK] {label} -> reverted: {e.message if hasattr(e, 'message') else e}")


def main():
    w3 = connect()
    c = load_deployed(w3)
    acc = w3.eth.accounts
    hotel, guest, guest2 = acc[HOTEL], acc[GUEST], acc[GUEST_2]
    print(f"Contract: {c.address}  (chain id {w3.eth.chain_id})")
    print(f"Hotel  (receiver): {hotel}")
    print(f"Guest  (sender)  : {guest}")
    print(f"Guest 2          : {guest2}")

    title("1. Hotel registers and publishes its rooms")
    send(w3, c.functions.registerHotel("Liffey View Hotel"), hotel)
    send(w3, c.functions.addRoom("Double room, city view", w3.to_wei(0.05, "ether")), hotel)
    send(w3, c.functions.addRoom("Single room", w3.to_wei(0.03, "ether")), hotel)
    for rid in c.functions.getHotelRooms(hotel).call():
        r = c.functions.getRoom(rid).call()
        print(f"  Room {r[0]}: {r[2]} - {eth(w3, r[3])} per night")

    today = c.functions.today().call()
    print(f"  Today (day number) = {today}")

    title("2. Guest books room 1 for 2 nights - money goes to the contract (escrow)")
    price = c.functions.quotePrice(1, today, today + 2).call()
    data_hash = guest_data_hash("Jane Doe", "P1234567", "random-salt-42")
    print(f"  Quote: {eth(w3, price)} | guest data hash: 0x{data_hash.hex()}")
    receipt = send(w3, c.functions.bookRoom(1, today, today + 2, data_hash), guest, price)
    event = c.events.RoomBooked().process_receipt(receipt)[0]["args"]
    print(f"  Event RoomBooked -> bookingId={event['bookingId']} amount={event['amount']}")
    print(f"  Tx hash 0x{receipt.transactionHash.hex()} | gas used {receipt.gasUsed}")
    show_booking(c, 1)
    print(f"  Escrow balance in contract: {eth(w3, c.functions.escrowBalance().call())}")

    title("3. Rules enforced by the contract")
    expect_revert("Double booking of the same night", c.functions.bookRoom(1, today + 1, today + 3, data_hash),
                  guest2, c.functions.quotePrice(1, today + 1, today + 3).call())
    expect_revert("Paying the wrong amount", c.functions.bookRoom(2, today, today + 1, data_hash),
                  guest2, 1)
    expect_revert("Someone else cancelling the guest's booking", c.functions.cancelBooking(1), guest2)
    wrong_sig = sign_check_in(c, 1, GUEST_2)
    expect_revert("Check-in with a signature from the wrong person", c.functions.checkIn(1, wrong_sig), hotel)

    title("4. Check-in: guest signs with private key (ECDSA), hotel submits it")
    sig = sign_check_in(c, 1, GUEST)
    print(f"  Guest signature: 0x{sig.hex()[:40]}...")
    send(w3, c.functions.checkIn(1, sig), hotel)
    show_booking(c, 1)
    print(f"  Hotel can now withdraw: {eth(w3, c.functions.pendingWithdrawals(hotel).call())}")

    title("5. Cancellation policy")
    p = c.functions.quotePrice(2, today + 5, today + 7).call()
    send(w3, c.functions.bookRoom(2, today + 5, today + 7, data_hash), guest2, p)
    r = send(w3, c.functions.cancelBooking(2), guest2)
    ev = c.events.BookingCancelled().process_receipt(r)[0]["args"]
    print(f"  Early cancel (>48h): refund {eth(w3, ev['refundToGuest'])}, fee {eth(w3, ev['feeToHotel'])}")

    p = c.functions.quotePrice(2, today + 1, today + 2).call()
    send(w3, c.functions.bookRoom(2, today + 1, today + 2, data_hash), guest, p)
    r = send(w3, c.functions.cancelBooking(3), guest)
    ev = c.events.BookingCancelled().process_receipt(r)[0]["args"]
    print(f"  Late cancel (<48h): refund {eth(w3, ev['refundToGuest'])}, fee {eth(w3, ev['feeToHotel'])}")

    title("6. Hotel rejects a booking -> full refund")
    p = c.functions.quotePrice(2, today + 10, today + 12).call()
    send(w3, c.functions.bookRoom(2, today + 10, today + 12, data_hash), guest2, p)
    send(w3, c.functions.rejectBooking(4), hotel)
    show_booking(c, 4)

    title("7. No-show (clock moved 3 days forward on Ganache)")
    p = c.functions.quotePrice(2, today + 1, today + 2).call()
    send(w3, c.functions.bookRoom(2, today + 1, today + 2, data_hash), guest2, p)
    expect_revert("No-show before the check-in day ended", c.functions.markNoShow(5), hotel)
    time_travel(w3, 3)
    send(w3, c.functions.markNoShow(5), hotel)
    show_booking(c, 5)

    title("8. Everyone withdraws their own money (pull payments)")
    for name, who in [("Hotel", hotel), ("Guest", guest), ("Guest 2", guest2)]:
        owed = c.functions.pendingWithdrawals(who).call()
        before = w3.eth.get_balance(who)
        send(w3, c.functions.withdraw(), who)
        print(f"  {name:8} withdrew {eth(w3, owed)} (wallet {eth(w3, before)} -> {eth(w3, w3.eth.get_balance(who))})")
    print(f"  Escrow balance left in contract: {eth(w3, c.functions.escrowBalance().call())}")

    title("Summary of bookings")
    for i in range(1, c.functions.bookingCount().call() + 1):
        show_booking(c, i)


if __name__ == "__main__":
    main()