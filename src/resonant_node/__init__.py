"""
ResonantGenesis Node
====================
Runtime node for the decentralized AI agent network.

Node Types:
- Runtime Node: Executes agents in sandboxed environments
- Index Node: Indexes and caches chain data for discovery
- Storage Node: Hosts agent code and memory via IPFS
- Gateway Node: Exposes REST/GraphQL APIs
"""

__version__ = "0.1.0"
__author__ = "ResonantGenesis"

from .core.node import ResonantNode, NodeConfig, NodeMode
from .core.identity import NodeIdentity

__all__ = [
    "ResonantNode",
    "NodeConfig", 
    "NodeMode",
    "NodeIdentity",
    "__version__",
]
