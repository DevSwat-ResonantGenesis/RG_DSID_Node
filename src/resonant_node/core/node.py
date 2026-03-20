"""
Main Node Orchestrator
======================
Coordinates all node components and manages lifecycle.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
import logging

from resonant_node.core.identity import NodeIdentity

logger = logging.getLogger(__name__)


class NodeMode(Enum):
    """Node operation modes."""
    RUNTIME = "runtime"      # Execute agents
    INDEX = "index"          # Index chain data
    STORAGE = "storage"      # Host content
    GATEWAY = "gateway"      # API endpoint
    FULL = "full"            # All of the above


@dataclass
class NodeConfig:
    """Node configuration."""
    mode: NodeMode = NodeMode.FULL
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    
    # Chain configuration
    chain_rpc: str = "https://sepolia.base.org"
    identity_contract: str = ""
    agent_contract: str = ""
    memory_contract: str = ""
    
    # Storage configuration
    ipfs_gateway: str = "https://ipfs.io/ipfs/"
    ipfs_api: Optional[str] = None
    
    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    
    # Runtime configuration
    max_concurrent_executions: int = 10
    default_timeout: int = 300
    sandbox_enabled: bool = True
    
    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090


class ResonantNode:
    """
    Main node orchestrator.
    
    Manages the lifecycle of all node components based on the configured mode.
    """
    
    def __init__(self, config: NodeConfig):
        self.config = config
        self.identity: Optional[NodeIdentity] = None
        self._running = False
        self._tasks: list[asyncio.Task] = []
        
        # Components (initialized based on mode)
        self._chain_client = None
        self._runtime = None
        self._indexer = None
        self._storage = None
        self._api = None
        
        # Ensure data directory exists
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> None:
        """Initialize node components."""
        logger.info(f"Initializing node in {self.config.mode.value} mode...")
        
        # Load or create node identity
        self.identity = await NodeIdentity.load_or_create(
            self.config.data_dir / "identity"
        )
        logger.info(f"Node identity: {self.identity.dsid}")
        
        # Initialize chain client
        from resonant_node.chain.client import ChainClient
        self._chain_client = ChainClient(
            rpc_url=self.config.chain_rpc,
            identity_contract=self.config.identity_contract,
            agent_contract=self.config.agent_contract,
            memory_contract=self.config.memory_contract,
        )
        await self._chain_client.connect()
        logger.info("Chain client connected")
        
        # Initialize components based on mode
        if self.config.mode in [NodeMode.RUNTIME, NodeMode.FULL]:
            from resonant_node.runtime.executor import AgentRuntime
            self._runtime = AgentRuntime(
                chain_client=self._chain_client,
                ipfs_gateway=self.config.ipfs_gateway,
                data_dir=self.config.data_dir / "agents",
                max_concurrent=self.config.max_concurrent_executions,
                default_timeout=self.config.default_timeout,
                sandbox_enabled=self.config.sandbox_enabled,
            )
            logger.info("Agent runtime initialized")
        
        if self.config.mode in [NodeMode.INDEX, NodeMode.FULL]:
            from resonant_node.chain.indexer import ChainIndexer
            self._indexer = ChainIndexer(
                chain_client=self._chain_client,
                data_dir=self.config.data_dir / "index",
            )
            logger.info("Chain indexer initialized")
        
        if self.config.mode in [NodeMode.STORAGE, NodeMode.FULL]:
            from resonant_node.storage.ipfs import StorageManager
            self._storage = StorageManager(
                ipfs_gateway=self.config.ipfs_gateway,
                ipfs_api=self.config.ipfs_api,
                data_dir=self.config.data_dir / "storage",
            )
            logger.info("Storage manager initialized")
        
        if self.config.mode in [NodeMode.GATEWAY, NodeMode.FULL]:
            from resonant_node.api.server import APIServer
            self._api = APIServer(
                host=self.config.api_host,
                port=self.config.api_port,
                runtime=self._runtime,
                indexer=self._indexer,
                storage=self._storage,
            )
            logger.info("API server initialized")
        
        logger.info("Node initialization complete")
    
    async def start(self) -> None:
        """Start the node."""
        if self._running:
            logger.warning("Node is already running")
            return
        
        self._running = True
        logger.info("Starting node...")
        
        # Start components
        if self._runtime:
            task = asyncio.create_task(self._runtime.start())
            self._tasks.append(task)
            logger.info("Runtime started")
        
        if self._indexer:
            task = asyncio.create_task(self._indexer.start())
            self._tasks.append(task)
            logger.info("Indexer started")
        
        if self._storage:
            task = asyncio.create_task(self._storage.start())
            self._tasks.append(task)
            logger.info("Storage started")
        
        if self._api:
            task = asyncio.create_task(self._api.start())
            self._tasks.append(task)
            logger.info(f"API server started on {self.config.api_host}:{self.config.api_port}")
        
        logger.info("Node is running")
        
        # Wait for all tasks
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
    
    async def stop(self) -> None:
        """Stop the node gracefully."""
        if not self._running:
            return
        
        logger.info("Stopping node...")
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Stop components in reverse order
        if self._api:
            await self._api.stop()
            logger.info("API server stopped")
        
        if self._storage:
            await self._storage.stop()
            logger.info("Storage stopped")
        
        if self._indexer:
            await self._indexer.stop()
            logger.info("Indexer stopped")
        
        if self._runtime:
            await self._runtime.stop()
            logger.info("Runtime stopped")
        
        if self._chain_client:
            await self._chain_client.disconnect()
            logger.info("Chain client disconnected")
        
        self._tasks.clear()
        logger.info("Node stopped")
    
    @property
    def status(self) -> dict:
        """Get node status."""
        return {
            "running": self._running,
            "mode": self.config.mode.value,
            "identity": self.identity.dsid if self.identity else None,
            "chain_connected": self._chain_client.connected if self._chain_client else False,
            "runtime_active": self._runtime.active if self._runtime else False,
            "indexer_synced": self._indexer.synced if self._indexer else False,
            "api_port": self.config.api_port if self._api else None,
        }
    
    @property
    def runtime(self):
        """Get runtime component."""
        return self._runtime
    
    @property
    def chain_client(self):
        """Get chain client."""
        return self._chain_client
