Blockchain CA1 - CCT College Dublin  
Student: Adriel Kampa de Gois - 2024378

This is a decentralized system for hotel bookings. A guest starts a booking and pays. The hotel then provides the room. The `HotelBooking` smart contract acts between both sides. It holds the money in escrow and sends it out based on the agreed booking rules.

## Main features
### Escrow payment
`bookRoom` is `payable`. The funds sit in the contract. They stay there until the booking ends by check-in, cancellation, rejection, or no-show.
### Prevent double booking
Each room and each day is tracked in `nightTaken[roomId][day]`. That locking stops the same night from being booked twice.
### Cancellation policy
If the guest cancels at least 48 hours before check-in, the guest can cancel for free. If it is later than that, a 50% fee applies.
### Hotel rejection
The hotel can reject a booking. In that case, the guest gets a full refund of 100%.
### ECDSA check-in
For check-in, the guest signs a check-in message. The contract verifies it using `ecrecover` before it pays the hotel.
### No-show
If the guest does not show up, after the check-in day the hotel can claim the payment.
### Privacy
On-chain storage keeps only a salted Keccak-256 hash of the guest details. The raw guest data is not stored.
### Safe payments
The contract uses a pull payment style, with `withdraw`. It also uses a re-entrancy guard. Solidity 0.8 overflow checks help reduce arithmetic issues.

## Project structure

```
contracts/HotelBooking.sol      smart contract (Solidity 0.8.20)
scripts/common.py               shared helpers (connect, compile, deploy, sign)
scripts/compile.py              compiles the contract with py-solc-x -> build/
scripts/deploy.py               deploys to Ganache, saves build/deployment.json
scripts/interact.py             full booking scenario (sender -> contract -> receiver)
scripts/sign_checkin.py         creates the guest signature to paste into Remix
scripts/start_ganache.sh        starts Ganache with a fixed mnemonic
scripts/pick_python.sh          finds a working python command (used by the .sh files)
tests/test_hotel_booking.py     20 automated tests (pytest)
notebook/HotelBooking_Demo.ipynb  step-by-step demo in Jupyter
setup.sh / run_demo.sh / run_tests.sh   shell scripts
docs/REMIX_GUIDE.md             how to test the contract in Remix IDE with Ganache
poster/BookChain_Poster.pptx    poster presentation
```

## Requirements

* Python 3.10+
* Node.js 18+ (for Ganache)
* Git Bash (on Windows) to run the `.sh` scripts
* Remix IDE: https://remix.ethereum.org

## How to run

```bash
./setup.sh                      # one time: .venv + Python packages + Ganache
./scripts/start_ganache.sh      # terminal 1 - leave it running
./run_demo.sh                   # terminal 2 - compile, deploy and run the scenario
./run_tests.sh                  # terminal 2 - automated tests
```

Notebook: `.venv/Scripts/python -m notebook notebook/HotelBooking_Demo.ipynb`

> `interact.py` moves the Ganache clock 3 days forward to test the no-show rule. Restart Ganache if you want "today" back to the real date.

## Ganache accounts used

Ganache is started with the test mnemonic `test test test test test test test test test test test junk` (test only).

Index | Role | Address

0 | Deployer | 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
1 | Hotel receiver | 0x70997970C51812dc3A010C7d01b50e0d17dc79C8
2 | Guest sender | 0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC
3 | Second guest | 0x90F79bf6EB2c4f870365E785982E1f101E93b906

## Booking states
```
bookRoom + pay > Booked -- checkIn(valid guest signature) >   CheckedIn     (hotel paid)
                      cancelBooking (guest)              >>   Cancelled     (refund 100% / 50%)
                        rejectBooking (hotel)            >>   Rejected      (refund 100%)
                         markNoShow (after check-in day) >>   NoShow        (hotel paid)
```
## Cryptography

* **Keccak-256** – hash of the guest data (`guestDataHash`) and of the check-in message.
* **ECDSA (secp256k1)** – the guest signs `getCheckInMessageHash(bookingId)` (EIP-191 prefix). The message includes the contract address, chain id and booking id, so it cannot be replayed on another booking or network. `recoverSigner` also rejects "high-s" signatures.

## Repository

GitHub:https://github.com/AdrielCCT/BookChain_Hotel-Booking-DApp