"""Automated test suite for the HotelBooking.sol smart contract.

Executed against a local Ganache instance (port 8545). Each test initializes
from an EVM snapshot and reverts upon completion to guarantee test isolation,
including scenarios involving time manipulation.
"""
import sys
from pathlib import Path

import pytest
from web3.exceptions import ContractLogicError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from common import (GUEST, GUEST_2, HOTEL, compile_contract, connect, deploy,  # noqa: E402
                    guest_data_hash, send, sign_check_in, time_travel)

BOOKED, CHECKED_IN, CANCELLED, REJECTED, NO_SHOW = 1, 2, 3, 4, 5
PRICE = 10**16  # 0.01 ETH per night
DATA_HASH = guest_data_hash("Test Guest", "X0000000", "salt")


@pytest.fixture(scope="session")
def w3():
    compile_contract()
    return connect()


@pytest.fixture
def setup(w3):
    snap = w3.provider.make_request("evm_snapshot", [])["result"]
    c, _ = deploy(w3)
    acc = w3.eth.accounts
    hotel, guest, guest2 = acc[HOTEL], acc[GUEST], acc[GUEST_2]
    send(w3, c.functions.registerHotel("Test Hotel"), hotel)
    send(w3, c.functions.addRoom("Room A", PRICE), hotel)
    today = c.functions.today().call()
    yield w3, c, hotel, guest, guest2, today
    w3.provider.make_request("evm_revert", [snap])


def book(w3, c, who, start, end, room=1):
    price = c.functions.quotePrice(room, start, end).call()
    send(w3, c.functions.bookRoom(room, start, end, DATA_HASH), who, price)
    return c.functions.bookingCount().call()


# --- Hotel and Room Registration ---

def test_hotel_registered_and_room_added(setup):
    w3, c, hotel, *_ = setup
    assert c.functions.hotelNames(hotel).call() == "Test Hotel"
    room = c.functions.getRoom(1).call()
    assert room[1] == hotel and room[3] == PRICE and room[4] is True


def test_only_registered_hotel_can_add_room(setup):
    w3, c, hotel, guest, *_ = setup
    with pytest.raises(ContractLogicError, match="Not a registered hotel"):
        c.functions.addRoom("Fake", PRICE).transact({"from": guest})


def test_hotel_cannot_register_twice(setup):
    w3, c, hotel, *_ = setup
    with pytest.raises(ContractLogicError, match="already registered"):
        c.functions.registerHotel("Again").transact({"from": hotel})


# --- Room Booking & Escrow Management ---

def test_booking_holds_money_in_escrow(setup):
    w3, c, hotel, guest, guest2, today = setup
    hotel_before = w3.eth.get_balance(hotel)
    bid = book(w3, c, guest, today, today + 3)
    b = c.functions.getBooking(bid).call()
    assert b[2] == guest and b[3] == hotel and b[8] == BOOKED
    assert b[6] == 3 * PRICE
    assert c.functions.escrowBalance().call() == 3 * PRICE
    assert w3.eth.get_balance(hotel) == hotel_before  # Hotel has not been paid yet
    assert b[7] == DATA_HASH  # Only the personal data hash is stored on-chain


def test_wrong_amount_rejected(setup):
    w3, c, hotel, guest, guest2, today = setup
    with pytest.raises(ContractLogicError, match="exact price"):
        c.functions.bookRoom(1, today, today + 2, DATA_HASH).transact({"from": guest, "value": PRICE})


def test_double_booking_rejected(setup):
    w3, c, hotel, guest, guest2, today = setup
    book(w3, c, guest, today + 1, today + 4)
    assert c.functions.isAvailable(1, today + 3, today + 5).call() is False
    with pytest.raises(ContractLogicError, match="already booked"):
        c.functions.bookRoom(1, today + 3, today + 5, DATA_HASH).transact(
            {"from": guest2, "value": 2 * PRICE})
    # Back-to-back stays are permitted as check-out dates are freed
    book(w3, c, guest2, today + 4, today + 6)


def test_invalid_dates_rejected(setup):
    w3, c, hotel, guest, guest2, today = setup
    with pytest.raises(ContractLogicError, match="after check-in"):
        c.functions.bookRoom(1, today + 2, today + 2, DATA_HASH).transact({"from": guest, "value": 0})
    with pytest.raises(ContractLogicError, match="in the past"):
        c.functions.bookRoom(1, today - 1, today + 1, DATA_HASH).transact({"from": guest, "value": 2 * PRICE})
    with pytest.raises(ContractLogicError, match="Too many nights"):
        c.functions.bookRoom(1, today, today + 31, DATA_HASH).transact({"from": guest, "value": 31 * PRICE})


def test_inactive_room_cannot_be_booked(setup):
    w3, c, hotel, guest, guest2, today = setup
    send(w3, c.functions.setRoomActive(1, False), hotel)
    with pytest.raises(ContractLogicError, match="Room not available"):
        c.functions.bookRoom(1, today, today + 1, DATA_HASH).transact({"from": guest, "value": PRICE})


# --- Check-in Verification (ECDSA Signatures) ---

def test_check_in_with_guest_signature_pays_hotel(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today, today + 2)
    sig = sign_check_in(c, bid, GUEST)
    send(w3, c.functions.checkIn(bid, sig), hotel)
    assert c.functions.getBooking(bid).call()[8] == CHECKED_IN
    assert c.functions.pendingWithdrawals(hotel).call() == 2 * PRICE


def test_check_in_with_wrong_signer_fails(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today, today + 2)
    fake = sign_check_in(c, bid, GUEST_2)
    with pytest.raises(ContractLogicError, match="Invalid guest signature"):
        c.functions.checkIn(bid, fake).transact({"from": hotel})


def test_signature_cannot_be_replayed_on_other_booking(setup):
    w3, c, hotel, guest, guest2, today = setup
    first = book(w3, c, guest, today, today + 1)
    second = book(w3, c, guest, today + 1, today + 2)
    sig_first = sign_check_in(c, first, GUEST)
    time_travel(w3, 1)
    with pytest.raises(ContractLogicError, match="Invalid guest signature"):
        c.functions.checkIn(second, sig_first).transact({"from": hotel})


def test_check_in_before_arrival_day_fails(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today + 3, today + 4)
    with pytest.raises(ContractLogicError, match="Outside the stay dates"):
        c.functions.checkIn(bid, sign_check_in(c, bid, GUEST)).transact({"from": hotel})


def test_only_hotel_of_booking_can_check_in(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today, today + 1)
    with pytest.raises(ContractLogicError, match="Not your booking"):
        c.functions.checkIn(bid, sign_check_in(c, bid, GUEST)).transact({"from": guest2})


# --- Cancellation, Rejection, and No-Show ---

def test_free_cancellation_more_than_48h_before(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today + 5, today + 7)
    send(w3, c.functions.cancelBooking(bid), guest)
    assert c.functions.pendingWithdrawals(guest).call() == 2 * PRICE
    assert c.functions.pendingWithdrawals(hotel).call() == 0
    assert c.functions.isAvailable(1, today + 5, today + 7).call() is True


def test_late_cancellation_pays_50_percent_fee(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today + 1, today + 3)
    send(w3, c.functions.cancelBooking(bid), guest)
    assert c.functions.pendingWithdrawals(guest).call() == PRICE
    assert c.functions.pendingWithdrawals(hotel).call() == PRICE


def test_only_guest_can_cancel(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today + 5, today + 6)
    with pytest.raises(ContractLogicError, match="Not your booking"):
        c.functions.cancelBooking(bid).transact({"from": guest2})


def test_hotel_rejects_booking_full_refund(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today + 1, today + 2)
    send(w3, c.functions.rejectBooking(bid), hotel)
    assert c.functions.getBooking(bid).call()[8] == REJECTED
    assert c.functions.pendingWithdrawals(guest).call() == PRICE


def test_no_show_only_after_check_in_day(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today + 1, today + 3)
    with pytest.raises(ContractLogicError, match="not finished"):
        c.functions.markNoShow(bid).transact({"from": hotel})
    time_travel(w3, 2)
    send(w3, c.functions.markNoShow(bid), hotel)
    assert c.functions.getBooking(bid).call()[8] == NO_SHOW
    assert c.functions.pendingWithdrawals(hotel).call() == 2 * PRICE


def test_cannot_cancel_after_check_in(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today, today + 1)
    send(w3, c.functions.checkIn(bid, sign_check_in(c, bid, GUEST)), hotel)
    with pytest.raises(ContractLogicError, match="not active"):
        c.functions.cancelBooking(bid).transact({"from": guest})


# --- Withdrawal & Escrow Settlement ---

def test_withdraw_sends_money_and_resets_balance(setup):
    w3, c, hotel, guest, guest2, today = setup
    bid = book(w3, c, guest, today, today + 2)
    send(w3, c.functions.checkIn(bid, sign_check_in(c, bid, GUEST)), hotel)
    before = w3.eth.get_balance(hotel)
    r = send(w3, c.functions.withdraw(), hotel)
    gas_cost = r.gasUsed * r.effectiveGasPrice
    assert w3.eth.get_balance(hotel) == before + 2 * PRICE - gas_cost
    assert c.functions.pendingWithdrawals(hotel).call() == 0
    assert c.functions.escrowBalance().call() == 0
    with pytest.raises(ContractLogicError, match="Nothing to withdraw"):
        c.functions.withdraw().transact({"from": hotel})