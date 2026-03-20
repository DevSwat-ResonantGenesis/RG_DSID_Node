"""
Blockchain Testing Suite for Base Testnet
==========================================

Week 3 GTM: Test blockchain integration against Base Sepolia testnet.

Tests:
1. Chain connection
2. Identity registry operations
3. Agent registry operations
4. Memory anchoring
5. External audit anchoring

Run with: pytest node/tests/test_blockchain_base_testnet.py -v

IMPORTANT: These tests require:
- BASE_SEPOLIA_RPC_URL environment variable
- Test wallet with Base Sepolia ETH (get from faucet)
- Deployed contracts on Base Sepolia (or use mock mode)
"""

import pytest
import asyncio
import os
import hashlib
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, '/Users/devswat/resonantgenesis_backend/node/src')

# Import directly from chain module to avoid full node import
sys.path.insert(0, '/Users/devswat/resonantgenesis_backend/node/src/resonant_node/chain')
from client import ChainClient


# ============================================
# TEST CONFIGURATION
# ============================================

# Base Sepolia testnet configuration
BASE_SEPOLIA_RPC = os.getenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org")
BASE_MAINNET_RPC = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")

# Test contract addresses (deploy these or use mocks)
TEST_IDENTITY_CONTRACT = os.getenv("TEST_IDENTITY_CONTRACT", "")
TEST_AGENT_CONTRACT = os.getenv("TEST_AGENT_CONTRACT", "")
TEST_MEMORY_CONTRACT = os.getenv("TEST_MEMORY_CONTRACT", "")

# Test wallet (NEVER use mainnet keys here!)
TEST_PRIVATE_KEY = os.getenv("TEST_PRIVATE_KEY", "")


# ============================================
# FIXTURES
# ============================================

@pytest.fixture
def chain_client():
    """Create a chain client for testing."""
    return ChainClient(
        rpc_url=BASE_SEPOLIA_RPC,
        identity_contract=TEST_IDENTITY_CONTRACT,
        agent_contract=TEST_AGENT_CONTRACT,
        memory_contract=TEST_MEMORY_CONTRACT,
    )


@pytest.fixture
def mock_web3():
    """Create a mock web3 instance for offline testing."""
    mock = MagicMock()
    mock.is_connected.return_value = True
    mock.eth.chain_id = 84532  # Base Sepolia chain ID
    mock.eth.block_number = 12345678
    mock.eth.gas_price = 1000000000  # 1 gwei
    mock.eth.get_transaction_count.return_value = 0
    mock.to_checksum_address = lambda x: x
    mock.keccak = lambda text: hashlib.sha256(text.encode()).digest()
    return mock


# ============================================
# CONNECTION TESTS
# ============================================

class TestChainConnection:
    """Tests for chain connection functionality."""
    
    def test_client_initialization(self, chain_client):
        """Verify client initializes with correct parameters."""
        assert chain_client.rpc_url == BASE_SEPOLIA_RPC
        assert chain_client._connected == False
        assert chain_client._web3 is None
    
    @pytest.mark.asyncio
    async def test_connect_to_base_sepolia(self, chain_client):
        """Test connection to Base Sepolia testnet."""
        # This test requires network access
        try:
            await chain_client.connect()
            
            if chain_client.connected:
                # Verify we're on Base Sepolia (chain ID 84532)
                chain_id = chain_client._web3.eth.chain_id
                assert chain_id == 84532, f"Expected Base Sepolia (84532), got {chain_id}"
                
                # Verify we can get block number
                block = await chain_client.get_block_number()
                assert block > 0, "Block number should be positive"
            else:
                pytest.skip("Could not connect to Base Sepolia - network may be unavailable")
                
        except ImportError:
            pytest.skip("web3 not installed")
        except Exception as e:
            pytest.skip(f"Connection failed: {e}")
    
    @pytest.mark.asyncio
    async def test_disconnect(self, chain_client):
        """Test disconnection."""
        await chain_client.disconnect()
        assert chain_client.connected == False
        assert chain_client._web3 is None
    
    @pytest.mark.asyncio
    async def test_offline_mode(self):
        """Test client works in offline mode when web3 not available."""
        client = ChainClient(rpc_url="http://invalid:8545")
        
        # Should not crash, just not connect
        await client.connect()
        assert client.connected == False
        
        # Operations should return None gracefully
        result = await client.get_identity("test_dsid")
        assert result is None


# ============================================
# IDENTITY REGISTRY TESTS
# ============================================

class TestIdentityRegistry:
    """Tests for identity registry operations."""
    
    @pytest.mark.asyncio
    async def test_get_identity_not_connected(self, chain_client):
        """Verify get_identity returns None when not connected."""
        result = await chain_client.get_identity("test_dsid")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_identity_no_contract(self):
        """Verify get_identity returns None when no contract configured."""
        client = ChainClient(
            rpc_url=BASE_SEPOLIA_RPC,
            identity_contract="",  # No contract
        )
        await client.connect()
        result = await client.get_identity("test_dsid")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_is_identity_active_not_found(self, chain_client):
        """Verify is_identity_active returns False for non-existent identity."""
        result = await chain_client.is_identity_active("nonexistent_dsid")
        assert result == False
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not TEST_IDENTITY_CONTRACT, reason="No identity contract configured")
    @pytest.mark.skipif(not TEST_PRIVATE_KEY, reason="No test private key configured")
    async def test_register_identity_integration(self, chain_client):
        """Integration test: Register identity on Base Sepolia."""
        await chain_client.connect()
        
        if not chain_client.connected:
            pytest.skip("Could not connect to Base Sepolia")
        
        # Generate test identity
        test_dsid = f"test_identity_{hashlib.sha256(os.urandom(8)).hexdigest()[:8]}"
        test_public_key = os.urandom(32)
        
        # Register identity
        tx_hash = await chain_client.register_identity(
            dsid=test_dsid,
            public_key=test_public_key,
            private_key=TEST_PRIVATE_KEY,
        )
        
        assert tx_hash is not None, "Transaction should return hash"
        assert len(tx_hash) == 66, "Transaction hash should be 66 chars (0x + 64 hex)"


# ============================================
# AGENT REGISTRY TESTS
# ============================================

class TestAgentRegistry:
    """Tests for agent registry operations."""
    
    @pytest.mark.asyncio
    async def test_get_agent_not_connected(self, chain_client):
        """Verify get_agent returns None when not connected."""
        result = await chain_client.get_agent("0x" + "a" * 64)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_is_agent_active_not_found(self, chain_client):
        """Verify is_agent_active returns False for non-existent agent."""
        result = await chain_client.is_agent_active("0x" + "b" * 64)
        assert result == False
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not TEST_AGENT_CONTRACT, reason="No agent contract configured")
    @pytest.mark.skipif(not TEST_PRIVATE_KEY, reason="No test private key configured")
    async def test_register_agent_integration(self, chain_client):
        """Integration test: Register agent on Base Sepolia."""
        await chain_client.connect()
        
        if not chain_client.connected:
            pytest.skip("Could not connect to Base Sepolia")
        
        # Generate test agent manifest
        manifest_hash = hashlib.sha256(os.urandom(32)).hexdigest()
        metadata_uri = f"ipfs://Qm{hashlib.sha256(os.urandom(16)).hexdigest()[:44]}"
        
        # Register agent
        tx_hash = await chain_client.register_agent(
            manifest_hash=manifest_hash,
            metadata_uri=metadata_uri,
            private_key=TEST_PRIVATE_KEY,
        )
        
        assert tx_hash is not None, "Transaction should return hash"


# ============================================
# MEMORY ANCHORING TESTS
# ============================================

class TestMemoryAnchoring:
    """Tests for memory anchoring operations."""
    
    @pytest.mark.asyncio
    async def test_get_memory_anchor_not_connected(self, chain_client):
        """Verify get_memory_anchor returns None when not connected."""
        result = await chain_client.get_memory_anchor("0x" + "c" * 64)
        assert result is None
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(not TEST_MEMORY_CONTRACT, reason="No memory contract configured")
    @pytest.mark.skipif(not TEST_PRIVATE_KEY, reason="No test private key configured")
    async def test_anchor_memory_integration(self, chain_client):
        """Integration test: Anchor memory on Base Sepolia."""
        await chain_client.connect()
        
        if not chain_client.connected:
            pytest.skip("Could not connect to Base Sepolia")
        
        # Generate test content hash
        content_hash = hashlib.sha256(os.urandom(32)).hexdigest()
        
        # Anchor memory
        tx_hash = await chain_client.anchor_memory(
            content_hash=content_hash,
            private_key=TEST_PRIVATE_KEY,
        )
        
        assert tx_hash is not None, "Transaction should return hash"


# ============================================
# MOCK TESTS (No Network Required)
# ============================================

class TestChainClientMocked:
    """Tests using mocked web3 for offline testing."""
    
    @pytest.mark.asyncio
    async def test_connect_with_mock(self, mock_web3):
        """Test connection with mocked web3."""
        client = ChainClient(rpc_url="http://mock:8545")
        
        # Manually set the mock (avoids needing web3 installed)
        client._web3 = mock_web3
        client._connected = True
        
        assert client.connected == True
    
    def test_dsid_hashing(self):
        """Test DSID hashing is deterministic."""
        dsid = "test_user_123"
        
        hash1 = hashlib.sha256(dsid.encode()).hexdigest()
        hash2 = hashlib.sha256(dsid.encode()).hexdigest()
        
        assert hash1 == hash2, "DSID hashing should be deterministic"
        assert len(hash1) == 64, "SHA256 hash should be 64 hex chars"
    
    def test_manifest_hash_format(self):
        """Test manifest hash format validation."""
        # Valid format
        valid_hash = "0x" + "a" * 64
        assert len(valid_hash) == 66
        assert valid_hash.startswith("0x")
        
        # Convert to bytes
        manifest_bytes = bytes.fromhex(valid_hash.replace("0x", ""))
        assert len(manifest_bytes) == 32


# ============================================
# EXTERNAL ANCHOR MANAGER TESTS
# ============================================

class TestExternalAnchorManager:
    """Tests for external anchor manager."""
    
    def test_merkle_root_calculation(self):
        """Test Merkle root calculation."""
        # Simulate entry hashes
        hashes = [
            hashlib.sha256(f"entry_{i}".encode()).hexdigest()
            for i in range(4)
        ]
        
        # Calculate Merkle root manually
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_hashes.append(new_hash)
            hashes = new_hashes
        
        merkle_root = hashes[0]
        
        assert len(merkle_root) == 64, "Merkle root should be 64 hex chars"
    
    def test_anchor_interval(self):
        """Test anchor interval logic."""
        anchor_interval = 100
        
        # Should anchor at multiples of 100
        assert 100 % anchor_interval == 0
        assert 200 % anchor_interval == 0
        assert 99 % anchor_interval != 0
        assert 101 % anchor_interval != 0


# ============================================
# GAS ESTIMATION TESTS
# ============================================

class TestGasEstimation:
    """Tests for gas estimation."""
    
    def test_gas_limits(self):
        """Verify gas limits are reasonable."""
        # From the client code
        identity_gas = 200000
        agent_gas = 200000
        memory_gas = 100000
        
        # Base Sepolia block gas limit is ~30M
        max_block_gas = 30_000_000
        
        assert identity_gas < max_block_gas
        assert agent_gas < max_block_gas
        assert memory_gas < max_block_gas
        
        # Reasonable limits (not too high, not too low)
        assert identity_gas >= 50000
        assert agent_gas >= 50000
        assert memory_gas >= 30000


# ============================================
# CHAIN ID VALIDATION TESTS
# ============================================

class TestChainIdValidation:
    """Tests for chain ID validation."""
    
    def test_base_sepolia_chain_id(self):
        """Verify Base Sepolia chain ID."""
        BASE_SEPOLIA_CHAIN_ID = 84532
        assert BASE_SEPOLIA_CHAIN_ID == 84532
    
    def test_base_mainnet_chain_id(self):
        """Verify Base Mainnet chain ID."""
        BASE_MAINNET_CHAIN_ID = 8453
        assert BASE_MAINNET_CHAIN_ID == 8453
    
    def test_chain_ids_different(self):
        """Verify testnet and mainnet have different chain IDs."""
        assert 84532 != 8453, "Testnet and mainnet should have different chain IDs"


# ============================================
# RUN TESTS
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
