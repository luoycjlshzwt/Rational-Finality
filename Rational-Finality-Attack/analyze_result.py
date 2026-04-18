import os
import sys
import re
import requests
import json
import time

def check_logs_for_events(log_dir):
    """ 
    1. leak_triggered (bool)
    2. reorg_depth (int, max depth)
    3. attack_triggered (bool)
    """
    beacon_log = os.path.join(log_dir, "beacon1", "beacon.log")

    if os.path.exists(os.path.join(log_dir, "beacon_logs.txt")):
        beacon_log = os.path.join(log_dir, "beacon_logs.txt")

    leak_triggered = False
    max_reorg_depth = 0
    
    if os.path.exists(beacon_log):
        with open(beacon_log, 'r') as f:
            for line in f:
                if "Inactivity leak" in line or "not finalizing" in line:
                    leak_triggered = True

                if "Chain reorg occurred" in line:
                    match = re.search(r'depth=(\d+)', line)
                    if match:
                        depth = int(match.group(1))
                        if depth > max_reorg_depth:
                            max_reorg_depth = depth
    
    attacker_log = os.path.join(log_dir, "attacker1", "d.log")
    attack_started = False
    if os.path.exists(attacker_log):
        with open(attacker_log, 'r') as f:
            if "Executing Inactivity Leak Attack" in f.read():
                attack_started = True

    return leak_triggered, max_reorg_depth, attack_started

def get_validator_balance(api_url, epoch, val_index):
    try:
        if epoch == "head":
            state_id = "head"
        else:
            state_id = int(epoch) * 32
            
        url = f"{api_url}/eth/v1/beacon/states/{state_id}/validators/{val_index}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return int(resp.json()['data']['balance'])
    except:
        pass
    return None

def main():
    # ResultDir, ApiUrl, HackCount, StartEpoch, Window
    if len(sys.argv) < 6:
        print("Usage: python3 analyze_result.py <Dir> <Url> <HackCount> <StartEpoch> <Window>")
        sys.exit(1)

    result_dir = sys.argv[1]
    api_url = sys.argv[2]
    hack_count = int(sys.argv[3])
    start_epoch = int(sys.argv[4])
    window = int(sys.argv[5])

    is_leak, depth, is_attack = check_logs_for_events(result_dir)

    
    end_epoch = start_epoch + window + 2
    try:
        head = requests.get(f"{api_url}/eth/v1/beacon/headers/head").json()
        curr_epoch = int(head['data']['header']['message']['slot']) // 32
        if curr_epoch < end_epoch:
            end_epoch = "head"
    except:
        end_epoch = "head"

    bal_start = get_validator_balance(api_url, start_epoch, 0)
    bal_end = get_validator_balance(api_url, end_epoch, 0)
    
    cost = 0
    if bal_start and bal_end:
        cost = bal_start - bal_end

    # Window, HackCount, AttackTriggered, LeakTriggered, MaxReorgDepth, Cost(Gwei)
    print(f"{window},{hack_count},{is_attack},{is_leak},{depth},{cost}")

if __name__ == "__main__":
    main()