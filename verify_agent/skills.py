# verify_agent/skills.py
from a2a import skill
import requests, os

@skill()
def verify_mint(tx_hash: str):
    url = (f"{os.getenv('BLOCKSCOUT')}"
           f"?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}")
    r = requests.get(url).json()
    return r.get("result", {}).get("status") == "0x1"
