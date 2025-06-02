# mint_agent/skills.py
from a2a import skill, call_remote
from web3 import Web3
w3 = Web3(Web3.HTTPProvider(os.getenv("WL_RPC")))
contract = w3.eth.contract(address=os.getenv("NFT_ADDR"), abi=ABI)

@skill()
def mint_and_verify_nft(photo_url: str, wallet: str):
    tx = contract.functions.mint(wallet, photo_url).transact()
    for _ in range(3):
        ok = call_remote("http://localhost:7001/jsonrpc",
                         "verifyMint", tx)
        if ok:
            return {"status":"success","tx":tx}
        tx = contract.functions.mint(wallet, photo_url).transact()
    return {"status":"fail"}
