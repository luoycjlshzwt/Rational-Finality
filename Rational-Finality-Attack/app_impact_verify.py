import time
import os
import sys
import web3
from web3 import Web3

RPC_URL = "http://localhost:8546"
CHAIN_ID = 32382
RAW_SENDER_ADDR = "0x0059a6d58aaca086951828ca1672ccd0d35b7b7c"
PRIV_KEY = "0xbaaced79f0ee1b636572d49a3f55320d7555522e63f9578e15a675f4c0c2d430" 
RAW_RECEIVER_ADDR = "0xb1022539c837dc5c1b1c89bf6d5b3df632ea54a6" 
LOG_PATH = "./data/attacker1/d.log"

def main():
    print("[*] Connecting Geth RPC (http://localhost:8545)...")
    w3 = None
    for i in range(10):
        try:
            w3 = Web3(Web3.HTTPProvider(RPC_URL))
            if w3.is_connected():
                print("[!] Successfully connected to Geth RPC")
                break
        except:
            pass
        print(f"[*] Waiting for Geth to start... ({i+1}/10)")
        time.sleep(5)

    if not w3 or not w3.is_connected():
        print("[Error] Unable to connect to GethRPC. Check, please:")
        sys.exit(1)

    SENDER_ADDR = w3.to_checksum_address(RAW_SENDER_ADDR)
    RECEIVER_ADDR = w3.to_checksum_address(RAW_RECEIVER_ADDR)

    initial_bal = w3.from_wei(w3.eth.get_balance(SENDER_ADDR), 'ether')
    print(f"[*] Initial balance: {initial_bal} ETH")

    print("[*] Monitoring logs, waiting ATTACK_TRIGGERED_EVENT...")
    while True:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, 'r') as f:
                if "!!! ATTACK_TRIGGERED_EVENT !" in f.read():
                    print("[!] Trigger signal captured! Send 2 ETH deposit transaction immediately...")
                    break
        time.sleep(1)

    tx = {
        'nonce': w3.eth.get_transaction_count(SENDER_ADDR),
        'to': RECEIVER_ADDR,
        'value': w3.to_wei(2, 'ether'),
        'gas': 21000,
        'gasPrice': w3.eth.gas_price,
        'chainId': CHAIN_ID
    }
    signed_tx = w3.eth.account.sign_transaction(tx, PRIV_KEY)
    try:
        raw_tx = signed_tx.raw_transaction
    except AttributeError:
        raw_tx = signed_tx.rawTransaction

    try:
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        print(f"[*] Transaction sent successfully! Hash: {tx_hash.hex()}", flush=True)
    except Exception as e:
        if "already known" in str(e):
            tx_hash = signed_tx.hash
            print(f"[*] The transaction is already in the mempool (already known). Hash: {tx_hash.hex()}", flush=True)
        else:
            print(f"[Error] Transaction sending failed: {e}", flush=True)
            sys.exit(1)

    print("[*] Recharging, waiting for 16 blocks to confirm...")
    mid_bal = initial_bal
    while True:
        try:
            print(f"[*] Waiting for transaction {tx_hash.hex()} to be packaged...")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120, poll_latency=1)
            print("[*] The transaction has been uploaded to the chain!")
        except web3.exceptions.TimeExceeded:
            print("[!] Wait timeout, transaction may still be pending or may have been dropped")
        except Exception as e:
            print(f"[!] An error occurred: {e}")
        if receipt:
            confirms = w3.eth.block_number - receipt['blockNumber']
            if confirms >= 16:
                mid_bal = w3.from_wei(w3.eth.get_balance(SENDER_ADDR), 'ether')
                mid_bal1 = w3.from_wei(w3.eth.get_balance(RECEIVER_ADDR), 'ether')
                print(f"[!] Confirm that the number is up to standard ({confirms}). Current balance: {mid_bal} ETH")
                print(f"[!] RECEIVER_ADDR. Current balance: {mid_bal1} ETH")
                break
        time.sleep(3)

    print("[*] Entering the monitoring stage: waiting for reorganization to roll back the balance...")

    max_seen_block = w3.eth.block_number
    while True:
        try:
            curr_block = w3.eth.block_number
            curr_bal = w3.from_wei(w3.eth.get_balance(SENDER_ADDR), 'ether')
            curr_bal1 = w3.from_wei(w3.eth.get_balance(RECEIVER_ADDR), 'ether')
            if curr_block < max_seen_block:
                print(f"[!!!] Execution layer block high bounce detected! {max_seen_block} -> {curr_block}", flush=True)
            max_seen_block = max(max_seen_block, curr_block)

            if curr_bal > mid_bal:
                print("!!! Experiment successful !!!")
                print(f"State rollback: {mid_bal} ETH (Transaction confirmed) -> {curr_bal} ETH (After reorganization)")
                print(f"State rollback: {mid_bal1} ETH (RECEIVER_ADDR) -> {curr_bal1} ETH (After reorganization)")
                print(f"Final result: The sender's assets are not lost, but the previous transaction has been recognized by the application layer.")
                
                with open("SUCCESS_DOUBLE_SPEND.txt", "w") as f:
                    f.write(f"Initial: {initial_bal}\nMid: {mid_bal}\nFinal: {curr_bal}\n")
                break
            print(f"| block height: {curr_block} | Current balance: {curr_bal} ETH | Waiting for rollback...", end='\r', flush=True)
            print(f"| block height: {curr_block} | RECEIVER_ADDR Current balance: {curr_bal1} ETH | Waiting for rollback...", end='\r', flush=True)
            
        except Exception as e:
            if "Connection refused" in str(e):
                print("\n[!] Container is closed, monitoring stopped.", flush=True)
                break
        time.sleep(2)

if __name__ == "__main__":
    main()
