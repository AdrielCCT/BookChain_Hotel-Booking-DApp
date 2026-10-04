"""Deploys HotelBooking to Ganache and saves the contract address into build/deployment.json."""
import json

from common import DEPLOYMENT_FILE, compile_contract, connect, deploy

if __name__ == "__main__":
    w3 = connect()
    compile_contract()
    contract, receipt = deploy(w3)
    info = {
        "address": contract.address,
        "chainId": w3.eth.chain_id,
        "deployer": receipt["from"],
        "txHash": "0x" + receipt.transactionHash.hex(),
        "block": receipt.blockNumber,
        "gasUsed": receipt.gasUsed,
    }
    DEPLOYMENT_FILE.write_text(json.dumps(info, indent=2))
    print("HotelBooking deployed")
    for k, v in info.items():
        print(f"  {k:9}: {v}")