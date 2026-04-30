# Rational Finality Attack: Experimental simulation and verification framework

This repository contains a complete set of automated experimental frameworks for verifying the security of Ethereum when subjected to a Rational Finality Attack. The core of the experiment is to create deep reorganization (Reorg) by inducing liveness failure (Liveness Stall) and demonstrate its asset rollback impact on the application layer (such as cross-chain bridges and exchanges).

## 1. Environment preparation

### Basic requirements

- operating system: Linux ( Ubuntu 20.04+ or WSL 2)
- Docker: 20.10.0+ and docker-compose (V2)
- Python: 3.8+

### Install dependencies

Execute the following command on the host machine to install the Python library required for the verification script:

```python
pip3 install web3 requests tqdm pandas matplotlib seaborn mesa
```

### Build image

Mirrors that need to be pulled manually:

```
docker pull tscel/geth:v1.13-base-v5
docker pull tscel/bf.prysm:v5.2.0-liveness
```

Or use GitHub Actions as a transfer station to download the image.

In addition, you need to enter the attacker-service directory and build the attacker service image:

```
cd attacker-service
make docker
```

------

## 2. Core Experiment: Deep Reorganization Verification

This experiment aims to verify whether the attacker can create a reorganization with a depth of more than 2 Epochs (64+slots) when the attacker occupies >33.3% Stake.

### Start experiment

Run the automation script `runtest.sh`. The script automatically generates the genesis block, configures the network, and starts the container.

```
./runtest.sh liveness
```

### Key parameter adjustment

+ Adjust in file `case/attack-liveness.yml` :

  ```
  entrypoint: attacker --config /root/config.toml --strategy liveness --max-hack-idx 6451 --logpath /root/attackerdata/d.log --loglevel debug
  ```

  The number 6451 represents the total number of attackers;

  ` VALIDATORS_NUM` in validator1 represents the total number of attackers;

  `VALIDATORS_INDEX` in validator1 represents the attacker’s index;

  ` VALIDATORS_NUM` in validator2 represents the number of honest validators;

  `VALIDATORS_INDEX` in validator2 represents the honest validator index.

+ Adjust in file `runtest.sh`:

  `caseduration` represents the experimental duration;

  `num-validators` represents the total number of validators.

### View results

After the experiment, the results are stored in `./results/liveness/`:

- Reorganization log: `grep "reorg event" data/beacon1/beacon.log`
- Transaction rollback: `app_impact_result.log`

------

## 3. ABM simulation

Since on-chain experiments run slowly, the Agent-Based Model based on the **Mesa** framework is used to verify the game theory equilibrium.

### Start simulation

```python
python3 liveness_simulation.py
python3 simulation.py
```

### Simulation variables

- $beta$(Bribe): The bribe provided by the attacker (as a proportion of the principal).
- $ell$(Window): Epoch length of attack duration.
- $X_{min}$: currency price after collapse (default 0.85).

------

## 4. Project structure description

- `/attacker-service`: Attacker strategy logic implementation (Go).
  - liveness/instance.go: Attack state machine and trigger logic.
  - liveness/block.go: Withholding policy for Slot 0.
- `/case`: Docker-compose: template file。
- `/config`: Genesis block configuration (`genesis.json`) and chain configuration (`config.yml`).
- `runtest.sh`: Core automated experiment scripts.
- `app_impact_verify.py`: Application layer transaction rollback detection Python script.
- `liveness_simulation.py`: Game theory phase transition simulation based on Mesa.

------

## 5. Notes

- Memory usage: When running 21,504 validators, please ensure that the host machine has at least 64 GB of memory.

- Data cleaning: Before each experiment, the script will automatically back up the old results directory. If the disk is insufficient, please clean it manually.

- Clock synchronization: If you use WSL 2, please ensure that its system time is synchronized with the Windows host, otherwise the Beacon node may not be able to produce blocks.
