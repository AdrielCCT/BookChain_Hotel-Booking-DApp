"""Shared helpers for the Hotel Booking DApp scripts.

Everything here talks to a local Ganache node. Ganache runs with a
fixed mnemonic (see start_ganache.sh) so we always get the exact same
accounts and private keys, which makes testing way easier.
"""
import json
import os
from pathlib import Path

import solcx
from eth_account import Account
from web3 import Web3

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_FILE = ROOT / "contracts" / "HotelBooking.sol"
BUILD_DIR = ROOT / "build"
ARTIFACT_FILE = BUILD_DIR / "HotelBooking.json"
DEPLOYMENT_FILE = BUILD_DIR / "deployment.json"

RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
SOLC_VERSION = "0.8.20"
EVM_VERSION = "paris"  # works on Ganache 7 and Remix

# Same mnemonic passed to Ganache in start_ganache.sh. Test only - never use
# this on mainnet!
MNEMONIC = os.getenv("MNEMONIC", "test test test test test test test test test test test junk")

# Roles used in the demo (index of the Ganache account)
HOTEL = 1
GUEST = 2
GUEST_2 = 3

ONE_DAY = 24 * 60 * 60


def connect():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise SystemExit(f"Cannot reach Ganache at {RPC_URL}. Run scripts/start_ganache.sh first.")
    return w3


def private_key(index):
    """Derive the private key for Ganache account <index> from the mnemonic."""
    Account.enable_unaudited_hdwallet_features()
    acct = Account.from_mnemonic(MNEMONIC, account_path=f"m/44'/60'/0'/0/{index}")
    return acct.key


def compile_contract():
    solcx.install_solc(SOLC_VERSION)
    source = CONTRACT_FILE.read_text(encoding="utf-8")
    out = solcx.compile_standard(
        {
            "language": "Solidity",
            "sources": {"HotelBooking.sol": {"content": source}},
            "settings": {
                "evmVersion": EVM_VERSION,
                "optimizer": {"enabled": True, "runs": 200},
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
            },
        },
        solc_version=SOLC_VERSION,
    )
    c = out["contracts"]["HotelBooking.sol"]["HotelBooking"]
    artifact = {"abi": c["abi"], "bytecode": c["evm"]["bytecode"]["object"]}
    BUILD_DIR.mkdir(exist_ok=True)
    ARTIFACT_FILE.write_text(json.dumps(artifact, indent=2))
    return artifact


def load_artifact():
    if not ARTIFACT_FILE.exists():
        return compile_contract()
    return json.loads(ARTIFACT_FILE.read_text())


def deploy(w3, deployer_index=0):
    art = load_artifact()
    factory = w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
    tx = factory.constructor().transact({"from": w3.eth.accounts[deployer_index]})
    receipt = w3.eth.wait_for_transaction_receipt(tx)
    return w3.eth.contract(address=receipt.contractAddress, abi=art["abi"]), receipt


def load_deployed(w3):
    if not DEPLOYMENT_FILE.exists():
        raise SystemExit("Contract not deployed yet. Run scripts/deploy.py first.")
    info = json.loads(DEPLOYMENT_FILE.read_text())
    return w3.eth.contract(address=info["address"], abi=load_artifact()["abi"])


def send(w3, fn, sender, value=0):
    """Send a transaction and wait until it gets mined."""
    tx = fn.transact({"from": sender, "value": value})
    return w3.eth.wait_for_transaction_receipt(tx)


def sign_check_in(contract, booking_id, guest_index):
    """Guest signs the check-in message off-chain using ECDSA secp256k1."""
    from eth_account.messages import encode_defunct

    msg_hash = contract.functions.getCheckInMessageHash(booking_id).call()
    signed = Account.sign_message(encode_defunct(primitive=msg_hash), private_key=private_key(guest_index))
    return signed.signature


def guest_data_hash(full_name, passport_no, salt):
    """Only this hash goes on-chain. The actual sensitive info stays with the hotel."""
    return Web3.solidity_keccak(["string", "string", "string"], [full_name, passport_no, salt])


def time_travel(w3, days):
    """Fast-forwards Ganache's clock (only works on a local test chain)."""
    w3.provider.make_request("evm_increaseTime", [int(days * ONE_DAY)])
    w3.provider.make_request("evm_mine", [])


def eth(w3, wei):
    return f"{w3.from_wei(wei, 'ether')} ETH"