"""
Chain Client
============
Interacts with Coordination Chain contracts.
"""

from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class ChainClient:
    """
    Client for interacting with Coordination Chain contracts.
    
    Provides methods to:
    - Query identity registry
    - Query agent registry
    - Query memory anchors
    - Submit transactions
    """
    
    def __init__(
        self,
        rpc_url: str,
        identity_contract: str = "",
        agent_contract: str = "",
        memory_contract: str = "",
    ):
        self.rpc_url = rpc_url
        self.identity_contract = identity_contract
        self.agent_contract = agent_contract
        self.memory_contract = memory_contract
        
        self._connected = False
        self._web3 = None
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    async def connect(self) -> None:
        """Connect to the chain."""
        try:
            from web3 import Web3
            from web3.middleware import geth_poa_middleware
            
            self._web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            self._web3.middleware_onion.inject(geth_poa_middleware, layer=0)
            
            self._connected = self._web3.is_connected()
            
            if self._connected:
                chain_id = self._web3.eth.chain_id
                block = self._web3.eth.block_number
                logger.info(f"Connected to chain {chain_id}, block {block}")
            else:
                logger.warning("Failed to connect to chain")
                
        except ImportError:
            logger.warning("web3 not installed, running in offline mode")
            self._connected = False
        except Exception as e:
            logger.error(f"Chain connection error: {e}")
            self._connected = False
    
    async def disconnect(self) -> None:
        """Disconnect from the chain."""
        self._web3 = None
        self._connected = False
    
    async def get_identity(self, dsid: str) -> Optional[dict]:
        """Get identity by DSID."""
        if not self._connected or not self.identity_contract:
            return None
        
        try:
            # IdentityRegistry ABI for getIdentity
            abi = [{
                "inputs": [{"name": "dsid", "type": "bytes32"}],
                "name": "getIdentity",
                "outputs": [
                    {"name": "owner", "type": "address"},
                    {"name": "publicKey", "type": "bytes"},
                    {"name": "status", "type": "uint8"},
                    {"name": "createdAt", "type": "uint256"},
                ],
                "stateMutability": "view",
                "type": "function"
            }]
            
            contract = self._web3.eth.contract(
                address=self._web3.to_checksum_address(self.identity_contract),
                abi=abi
            )
            
            dsid_bytes = self._web3.keccak(text=dsid)
            result = contract.functions.getIdentity(dsid_bytes).call()
            
            return {
                "dsid": dsid,
                "owner": result[0],
                "public_key": result[1].hex() if result[1] else None,
                "status": result[2],
                "created_at": result[3],
            }
        except Exception as e:
            logger.error(f"Failed to get identity {dsid}: {e}")
            return None
    
    async def get_agent(self, manifest_hash: str) -> Optional[dict]:
        """Get agent by manifest hash."""
        if not self._connected or not self.agent_contract:
            return None
        
        try:
            # AgentRegistry ABI for getAgent
            abi = [{
                "inputs": [{"name": "manifestHash", "type": "bytes32"}],
                "name": "getAgent",
                "outputs": [
                    {"name": "owner", "type": "address"},
                    {"name": "metadataUri", "type": "string"},
                    {"name": "status", "type": "uint8"},
                    {"name": "registeredAt", "type": "uint256"},
                ],
                "stateMutability": "view",
                "type": "function"
            }]
            
            contract = self._web3.eth.contract(
                address=self._web3.to_checksum_address(self.agent_contract),
                abi=abi
            )
            
            manifest_bytes = bytes.fromhex(manifest_hash.replace("0x", ""))
            result = contract.functions.getAgent(manifest_bytes).call()
            
            return {
                "manifest_hash": manifest_hash,
                "owner": result[0],
                "metadata_uri": result[1],
                "status": result[2],
                "registered_at": result[3],
            }
        except Exception as e:
            logger.error(f"Failed to get agent {manifest_hash}: {e}")
            return None
    
    async def get_memory_anchor(self, content_hash: str) -> Optional[dict]:
        """Get memory anchor by content hash."""
        if not self._connected or not self.memory_contract:
            return None
        
        try:
            # MemoryAnchors ABI for getAnchor
            abi = [{
                "inputs": [{"name": "contentHash", "type": "bytes32"}],
                "name": "getAnchor",
                "outputs": [
                    {"name": "owner", "type": "address"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "blockNumber", "type": "uint256"},
                ],
                "stateMutability": "view",
                "type": "function"
            }]
            
            contract = self._web3.eth.contract(
                address=self._web3.to_checksum_address(self.memory_contract),
                abi=abi
            )
            
            content_bytes = bytes.fromhex(content_hash.replace("0x", ""))
            result = contract.functions.getAnchor(content_bytes).call()
            
            return {
                "content_hash": content_hash,
                "owner": result[0],
                "timestamp": result[1],
                "block_number": result[2],
            }
        except Exception as e:
            logger.error(f"Failed to get memory anchor {content_hash}: {e}")
            return None
    
    async def is_identity_active(self, dsid: str) -> bool:
        """Check if identity is active."""
        identity = await self.get_identity(dsid)
        return identity is not None and identity.get("status") == 0
    
    async def is_agent_active(self, manifest_hash: str) -> bool:
        """Check if agent is active."""
        agent = await self.get_agent(manifest_hash)
        return agent is not None and agent.get("status") == 0
    
    async def get_block_number(self) -> int:
        """Get current block number."""
        if not self._connected:
            return 0
        return self._web3.eth.block_number
    
    # ============== Write Operations ==============
    
    async def register_identity(
        self,
        dsid: str,
        public_key: bytes,
        private_key: str,
    ) -> Optional[str]:
        """Register a new identity on-chain."""
        if not self._connected or not self.identity_contract:
            return None
        
        try:
            abi = [{
                "inputs": [
                    {"name": "dsid", "type": "bytes32"},
                    {"name": "publicKey", "type": "bytes"},
                ],
                "name": "registerIdentity",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }]
            
            contract = self._web3.eth.contract(
                address=self._web3.to_checksum_address(self.identity_contract),
                abi=abi
            )
            
            dsid_bytes = self._web3.keccak(text=dsid)
            account = self._web3.eth.account.from_key(private_key)
            
            tx = contract.functions.registerIdentity(dsid_bytes, public_key).build_transaction({
                'from': account.address,
                'nonce': self._web3.eth.get_transaction_count(account.address),
                'gas': 200000,
                'gasPrice': self._web3.eth.gas_price,
            })
            
            signed = account.sign_transaction(tx)
            tx_hash = self._web3.eth.send_raw_transaction(signed.rawTransaction)
            
            logger.info(f"Registered identity {dsid}, tx: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to register identity {dsid}: {e}")
            return None
    
    async def register_agent(
        self,
        manifest_hash: str,
        metadata_uri: str,
        private_key: str,
    ) -> Optional[str]:
        """Register a new agent on-chain."""
        if not self._connected or not self.agent_contract:
            return None
        
        try:
            abi = [{
                "inputs": [
                    {"name": "manifestHash", "type": "bytes32"},
                    {"name": "metadataUri", "type": "string"},
                ],
                "name": "registerAgent",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }]
            
            contract = self._web3.eth.contract(
                address=self._web3.to_checksum_address(self.agent_contract),
                abi=abi
            )
            
            manifest_bytes = bytes.fromhex(manifest_hash.replace("0x", ""))
            account = self._web3.eth.account.from_key(private_key)
            
            tx = contract.functions.registerAgent(manifest_bytes, metadata_uri).build_transaction({
                'from': account.address,
                'nonce': self._web3.eth.get_transaction_count(account.address),
                'gas': 200000,
                'gasPrice': self._web3.eth.gas_price,
            })
            
            signed = account.sign_transaction(tx)
            tx_hash = self._web3.eth.send_raw_transaction(signed.rawTransaction)
            
            logger.info(f"Registered agent {manifest_hash}, tx: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to register agent {manifest_hash}: {e}")
            return None
    
    async def anchor_memory(
        self,
        content_hash: str,
        private_key: str,
    ) -> Optional[str]:
        """Anchor a memory hash on-chain."""
        if not self._connected or not self.memory_contract:
            return None
        
        try:
            abi = [{
                "inputs": [{"name": "contentHash", "type": "bytes32"}],
                "name": "anchor",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }]
            
            contract = self._web3.eth.contract(
                address=self._web3.to_checksum_address(self.memory_contract),
                abi=abi
            )
            
            content_bytes = bytes.fromhex(content_hash.replace("0x", ""))
            account = self._web3.eth.account.from_key(private_key)
            
            tx = contract.functions.anchor(content_bytes).build_transaction({
                'from': account.address,
                'nonce': self._web3.eth.get_transaction_count(account.address),
                'gas': 100000,
                'gasPrice': self._web3.eth.gas_price,
            })
            
            signed = account.sign_transaction(tx)
            tx_hash = self._web3.eth.send_raw_transaction(signed.rawTransaction)
            
            logger.info(f"Anchored memory {content_hash}, tx: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to anchor memory {content_hash}: {e}")
            return None
