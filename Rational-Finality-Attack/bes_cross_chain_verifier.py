import time, os, requests, json
from web3 import Web3
from solcx import install_solc, compile_source


SRC_RPC = "http://localhost:8546"     
SRC_BEACON = "http://localhost:34001"  
DST_RPC = "http://localhost:8547"      # Anvil

CHAIN_ID_SRC = 32382
SENDER_ADDR = Web3.to_checksum_address("0x0059a6d58aaca086951828ca1672ccd0d35b7b7c")
SENDER_KEY = "0xbaaced79f0ee1b636572d49a3f55320d7555522e63f9578e15a675f4c0c2d430"
# SENDER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
RECEIVER_DST = Web3.to_checksum_address("0x70997970C51812dc3A010C7d01b50e0d17dc79C8")
# 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
# contract setting
# CONTRACT_ADDR = None 
contract_source_code = '''
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.18;

contract BESBridge {
    struct PendingTransfer {
        uint256 blockNum;
        bytes32 blockHash;
        uint256 amount;
        address receiver;
        bool resolved;
    }
    uint256 public totalBond; 
    uint256 public reserved;  
    mapping(bytes32 => PendingTransfer) public transfers;

    function depositBond() external payable { totalBond += msg.value; }

    function earlyExecute(bytes32 txHash, uint256 bn, bytes32 bh, address ai, uint256 vi) external {
        require(totalBond - reserved >= vi, "Bond insufficient");
        reserved += vi;
        transfers[txHash] = PendingTransfer(bn, bh, vi, ai, false);
        payable(ai).transfer(vi);
    }

    function resolve(bytes32 txHash, bytes32 actualFinalizedHash) external {
        PendingTransfer storage t = transfers[txHash];
        require(t.amount > 0 && !t.resolved, "Invalid");
        if (actualFinalizedHash == t.blockHash) {
            reserved -= t.amount;
        } else {
            reserved -= t.amount;
            totalBond -= t.amount;
        }
        t.resolved = true;
    }
}
'''

def print_balance_dashboard(stage_name, w3_src, w3_dst, bes_contract):
    """Prints a formatted dashboard of all relevant balances across both chains."""
    print(f"\n" + "="*10)
    print(f" BALANCE DASHBOARD - {stage_name}")
    print("="*10)
    
    # Source Chain Balances
    src_sender_bal = w3_src.from_wei(w3_src.eth.get_balance(SENDER_ADDR), 'ether')
    print(f"[Source Chain] Sender Balance:   {src_sender_bal:.4f} ETH")
    
    # Destination Chain Balances
    dst_receiver_bal = w3_dst.from_wei(w3_dst.eth.get_balance(RECEIVER_DST), 'ether')
    total_bond = w3_dst.from_wei(bes_contract.functions.totalBond().call(), 'ether')
    reserved_bond = w3_dst.from_wei(bes_contract.functions.reserved().call(), 'ether')
    
    print(f"[Target Chain] Receiver Balance: {dst_receiver_bal:.4f} ETH")
    print(f"[Target Chain] BES Bond (R):     {total_bond:.4f} ETH")
    print(f"[Target Chain] Reserved (E):     {reserved_bond:.4f} ETH")
    print("="*10 + "\n")

def deploy_contract(w3):
    print("[*] Deploying BES contract in target chain (Anvil)...")
    install_solc("0.8.18")
    compiled_sol = compile_source(contract_source_code, solc_version="0.8.18")
    contract_id, contract_interface = compiled_sol.popitem()
    
    #Use Anvil default first account (auto-signed by Anvil)
    deployer = w3.eth.accounts[0]
    BES = w3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])
    tx_hash = BES.constructor().transact({'from': deployer})
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"[!] Contract deployed in target chain: {tx_receipt.contractAddress}")
    
    # initialize
    bes_instance = w3.eth.contract(address=tx_receipt.contractAddress, abi=contract_interface['abi'])
    bes_instance.functions.depositBond().transact({'from': deployer, 'value': w3.to_wei(50, 'ether')})
    print("[!] Deposit 50ETH to target chain (R=50)")
    return bes_instance

# def get_finalized_epoch():
#     try:
#         res = requests.get(f"{SRC_BEACON}/eth/v1/beacon/states/head/finality_checkpoints")
#         return int(res.json()['data']['finalized']['epoch'])
#     except: return 0

def get_finalized_epoch():
    try:
        # 改用这个路径查看所有 checkpoint
        res = requests.get(f"{SRC_BEACON}/eth/v1/beacon/states/head/finality_checkpoints", timeout=5)
        data = res.json()['data']
        finalized = int(data['finalized']['epoch'])
        justified = int(data['current_justified']['epoch'])
        
        # 调试打印
        print(f"| API Check: Finalized={finalized}, Justified={justified} |", end='\r')
        
        return finalized
    except Exception as e:
        # print(f"API Error: {e}")
        return 0

def main():
    w3_src = Web3(Web3.HTTPProvider(SRC_RPC))
    w3_dst = Web3(Web3.HTTPProvider(DST_RPC))
    print(f"[*] Connecting to Target Chain (Anvil) at {DST_RPC}...", flush=True)
    connected = False
    for i in range(10):
        try:
            if w3_dst.is_connected():
                print("[!] Target Chain Connected!")
                connected = True
                break
        except:
            pass
        print(f"[*] Waiting for Anvil to start... ({i+1}/20)", flush=True)
        time.sleep(5)
    
    if not connected:
        print("[Error] Could not connect to Anvil on 8547. Check your Docker YAML!")
        return
    bes_contract = deploy_contract(w3_dst)
    print("[*] Monitoring source chain attack signals...")

    print_balance_dashboard("T0: INITIAL STATE", w3_src, w3_dst, bes_contract)
    
    log_path = "./data/attacker1/d.log"
    while True:
        if os.path.exists(log_path) and "!!! ATTACK_TRIGGERED_EVENT !" in open(log_path).read():
            break
        time.sleep(2)
    
    # 3. T1 start
    print(f"[*] Preparing transaction...", flush=True)
    nonce = w3_src.eth.get_transaction_count(SENDER_ADDR)
    tx = {
        'nonce': nonce, 
        'to': RECEIVER_DST, # Or any other address
        'value': w3_src.to_wei(10, 'ether'),
        'gas': 21000, 
        'gasPrice': w3_src.eth.gas_price, 
        'chainId': CHAIN_ID_SRC
    }
    
    signed = w3_src.eth.account.sign_transaction(tx, SENDER_KEY)
    # --- ADDED ERROR HANDLING HERE ---
    try:
        tx_hash = w3_src.eth.send_raw_transaction(signed.raw_transaction)
        print(f"[*] Transaction sent successfully! Hash: {tx_hash.hex()}", flush=True)
    except Exception as e:
        # Check if the error is "already known"
        if "already known" in str(e).lower():
            tx_hash = signed.hash # Use the hash from the signed object
            print(f"[*] Transaction is already in mempool (already known). Hash: {tx_hash.hex()}", flush=True)
        else:
            # If it's a real error (like insufficient funds), print and exit
            print(f"[ERROR] Failed to send transaction: {e}", flush=True)
            return 

    # 4. EarlyExecute
    tx_receipt_block = 0
    try:
        # This will wait until the tx is mined or timeout (e.g., 300 seconds)
        receipt = w3_src.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
        tx_receipt_block = receipt['blockNumber']
        print(f"[*] Transaction mined in block: {tx_receipt_block}", flush=True)
    except Exception as e:
        print(f"[ERROR] Transaction was not mined within timeout: {e}", flush=True)
        return
    recorded_hash = None
    print(f"[*] Monitoring confirmations (k=16)...", flush=True)

    while True:
        try:
            current_block = w3_src.eth.block_number
            confirms = current_block - tx_receipt_block
            
            if confirms >= 16:
                # Get the hash of the block where our transaction lived
                recorded_hash = w3_src.eth.get_block(tx_receipt_block)['hash']
                print(f"\n[Stage T1] Source Chain reached 16 confirmations (Current: {current_block}).")
                
                # Trigger Early Settlement on Target Chain
                print(f"[*] Triggering EarlyExecute on Anvil...", flush=True)
                tx_anvil_hash = bes_contract.functions.earlyExecute(
                    tx_hash, tx_receipt_block, recorded_hash, RECEIVER_DST, w3_src.to_wei(10, 'ether')
                ).transact({'from': w3_dst.eth.accounts[0]})

                print("[*] Waiting for Anvil to process EarlyExecute...", flush=True)
                w3_dst.eth.wait_for_transaction_receipt(tx_anvil_hash)
                
                print_balance_dashboard("T1: EARLY SETTLEMENT (PRE-REORG)", w3_src, w3_dst, bes_contract)
                break
            else:
                print(f"| Confirmations: {confirms}/16 | Current Block: {current_block} | Waiting...", end='\r', flush=True)
        except Exception as e:
            print(f"\n[*] Temporary error while checking confirmations: {e}", flush=True)
            
        time.sleep(5)

    # 5. T2
    target_epoch = (tx_receipt_block // 32) + 2
    print(f"[*] Waiting for the source chain Epoch {target_epoch} to be finalized for settlement...")
    while True:
        curr_finalized = get_finalized_epoch()
        if curr_finalized >= target_epoch:
            print(f"\n[T2] The source chain has been finalized.")
            # 6. Resolve
            try:
                final_block_hash = w3_src.eth.get_block(tx_receipt_block)['hash']
            except:
                final_block_hash = "0x0000000000000000000000000000000000000000"

            print(f"[*] Original hash: {recorded_hash}")
            print(f"[*] Final hash: {final_block_hash}")

            tx_res = bes_contract.functions.resolve(tx_hash, final_block_hash).transact({'from': w3_dst.eth.accounts[0]})
            w3_dst.eth.wait_for_transaction_receipt(tx_res)

            if final_block_hash != recorded_hash:
                print("!!! EXPERIMENT RESULT: REORG DETECTED & COMPENSATED !!!")
                print(f"The transaction was reverted on the Source Chain.")
                print(f"The BES Contract successfully paid out 10 ETH to the receiver from the bond.")
            else:
                print("[Result] No reorganization occurred, normal settlement.")
            print_balance_dashboard("T2: POST-REORG FINAL STATE", w3_src, w3_dst, bes_contract)
            break
        
        print(f"| Current Finalized Epoch: {curr_finalized} / Target: {target_epoch} | Waiting...", end='\r')
        time.sleep(15)

if __name__ == "__main__":
    main()
