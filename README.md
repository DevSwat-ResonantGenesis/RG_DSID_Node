# RG_DSID_Node

> **Part of the [DevSwat](https://resonant.dev-swat.com) platform** — External decentralized node runtime for agent execution, DSID anchoring on Base Sepolia, and P2P networking.

[![Status: Restored](https://img.shields.io/badge/Status-Restored-yellow.svg)]()
[![Port: 8081](https://img.shields.io/badge/Port-8081-orange.svg)]()
[![License: RG Source Available](https://img.shields.io/badge/License-RG%20Source%20Available-blue.svg)](LICENSE.txt)

**External** decentralized P2P node. Runs agents on-chain, indexes Base Sepolia data, manages IPFS storage, and provides sandboxed agent execution with governance.

> **Not to be confused with:**
> - **RG_DSID_Blockchain** — Internal platform blockchain (DSID-P ledger, audit chain, port 8000)
> - **RG_TrainingNet_Chain** — Training network chain (Raft consensus, block production)

## Features
- Agent execution runtime with governance decisions
- DSID anchoring on Base Sepolia (real L2)
- Chain indexing and transaction validation
- IPFS content storage
- Sandboxed agent execution
- CLI tools: `resonant-node`, `resonant-agent`, `resonant-key`
- REST API on port 8081

## Quick Start
```bash
pip install -e .
resonant-node --help
```

## Deployment
- **Container**: `dsid_node` | **Port**: 8081
- **Server path**: `/home/deploy/RG_DSID_Node`

---
**Organization**: [DevSwat-ResonantGenesis](https://github.com/DevSwat-ResonantGenesis) | **Platform**: [resonant.dev-swat.com](https://resonant.dev-swat.com)
