# Rational-Finality-Attack: Systematic Orchestration and Evaluation Framework

This repository provides a comprehensive framework for reproducing and evaluating the **Rational Finality Attack** on Ethereum-like Proof-of-Stake (PoS) systems. This framework is designed to demonstrate an attacker can cause deep chain reorganizations by inducing stall in activity.

## 1. Overview

The framework consists of a core attack strategy engine and an automated orchestration layer. It allows researchers to:

+ **Induce Liveness Stalls**: Systematically withhold blocks and attestations to prevent consensus finalization.

- **Trigger Deep Reorganizations**: Create and release long-range private forks (e.g., up to 94 blocks) to revert confirmed states.
- **Verify Application-Layer Risk**: Demonstrate real-world double-spend scenarios using a simulated asset gateway.

------

## 2. Repository Structure

The framework is organized into three logical tiers:

### 2.1 Attack Core Engine (/attacker-service)

The implementation of the malicious strategy logic, designed as a modular service for consensus clients.

- `Attacker-Service/library/liveness/liveness.go`: The attack state machine. It monitors epoch transitions and implements the triggering logic based on consecutive slot leadership.
- `Attacker-Service/library/liveness/block.go`: The execution module for targeted withholding. It manages the precision release of withheld blocks and the suppression of attestations for specific slots (e.g., Slot 0).

### 2.2 Orchestration & Deployment (/Rational-Finality-Attack)

Tools for environment setup and lifecycle management.

- `Rational-Finality-Attack/case/attack-liveness.yml`: A Docker Compose template for a heterogeneous network environment, integrating execution-layer clients (Geth) and consensus-layer nodes (Prysm).
- `Rational-Finality-Attack/runtest.sh`: The primary entry point for single-run experiments. It automates genesis generation, container deployment, and log harvesting.
- `Rational-Finality-Attack/app_impact_verify.py`: A Python-based verification tool that simulates a 'mock asset gateway'. It injects a transaction, waits for a predefined confirmation threshold (e.g., k=16), and detects state reversions following a reorganization.
- `Rational-Finality-Attack/analyze_result.py`: An analytical tool for calculating validator revenue and the impact of the 'Inactivity Leak' mechanism during prolonged stalls.
- `Rational-Finality-Attack/result/`: Experimental result files, including the experimental logs of each node and the results of the simulated asset gateway script execution.
- `Rational-Finality-Attack/config/`: Pre-configured genesis states, chain specifications, and security credentials (JWT).

### 2.3 Verification & Simulation (/Rational-Finality-Attack)

Modules for empirical measurement and theoretical validation.

- `Rational-Finality-Attack/liveness_simulation.py`: An Agent-Based Model (ABM) built on the **Mesa** framework to simulate 5,000 heterogeneous agents and observe the three-stage equilibrium transition.

## 3. Logical Workflow

The experimental evaluation follows a rigorous linear pipeline:

+ **Environment Initialization**: The orchestrator generates a unique genesis state and initializes a containerized network with the specified validator scale.
+ **Attack Triggering**: The attacker-service monitors proposer duties. Upon detecting a trigger condition (e.g., participation of rational validators meets expectations), it enters the Withholding phase.
+ **Application Injection**: As the attack starts, the verification script initiates a "deposit" transaction to a mock gateway on the honest fork.
+ **Confirmation and Action**: The gateway waits for $k$ confirmations on the honest chain and "releases" assets, treating the transaction as finalized.
+ **Reorganization and Reversal**: The attacker-service releases the withheld chain. The consensus layer triggers a deep reorganization, forcing the execution layer to revert its state.
+ **Data Analysis**: The framework collects logs to measure reorg depth, finality delay, and identifies the successful "double-spend" where the sender's balance reverts while the application action remains recorded.

------

## 4. Experimental Steps

For specific experiment startup information, please refer to the document `Rational-Finality-Attack/README.md`.

