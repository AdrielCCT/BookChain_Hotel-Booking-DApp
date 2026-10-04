"""Compiles contracts/HotelBooking.sol and saves the ABI + bytecode into build/."""
from common import ARTIFACT_FILE, SOLC_VERSION, compile_contract

if __name__ == "__main__":
    art = compile_contract()
    fns = [x["name"] for x in art["abi"] if x["type"] == "function"]
    print(f"Compiled with solc {SOLC_VERSION}")
    print(f"Bytecode size: {len(art['bytecode']) // 2} bytes")
    print(f"{len(fns)} functions: {', '.join(sorted(fns))}")
    print(f"Saved to {ARTIFACT_FILE}")