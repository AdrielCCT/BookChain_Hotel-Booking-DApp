"""Creates the guest's check-in signature so it can be pasted into Remix.

Usage:
    python scripts/sign_checkin.py <contract_address> <booking_id> [guest_account_index]

Example (contract deployed from Remix on Ganache, guest = account 2):
    python scripts/sign_checkin.py 0x5FbDB2315678afecb367f032d93F642f64180aa3 1 2

Copy the printed signature into the `guestSignature` field of checkIn in Remix.
"""
import sys

from web3 import Web3

from common import GUEST, connect, load_artifact, sign_check_in

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    address = Web3.to_checksum_address(sys.argv[1])
    booking_id = int(sys.argv[2])
    guest_index = int(sys.argv[3]) if len(sys.argv) > 3 else GUEST

    w3 = connect()
    contract = w3.eth.contract(address=address, abi=load_artifact()["abi"])
    guest = w3.eth.accounts[guest_index]
    booking = contract.functions.getBooking(booking_id).call()
    if booking[2] != guest:
        print(f"Warning: booking {booking_id} belongs to {booking[2]}, not {guest}")

    msg_hash = contract.functions.getCheckInMessageHash(booking_id).call()
    sig = sign_check_in(contract, booking_id, guest_index)
    print(f"Guest account   : {guest}")
    print(f"Private key used: account #{guest_index} from the Ganache mnemonic")
    print(f"Message hash    : 0x{msg_hash.hex()}")
    print(f"Signature       : 0x{sig.hex()}")