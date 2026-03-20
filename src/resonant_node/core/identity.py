"""
Node Identity Management
========================
DSID-P identity for node operations.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import hashlib

from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder


@dataclass
class NodeIdentity:
    """Node cryptographic identity."""
    
    dsid: str
    public_key: bytes
    private_key: bytes
    identity_type: str = "node"
    
    @classmethod
    async def load_or_create(cls, identity_dir: Path) -> "NodeIdentity":
        """Load existing identity or create new one."""
        identity_dir.mkdir(parents=True, exist_ok=True)
        identity_file = identity_dir / "identity.json"
        key_file = identity_dir / "private.key"
        
        if identity_file.exists() and key_file.exists():
            return cls._load(identity_file, key_file)
        
        return cls._create(identity_file, key_file)
    
    @classmethod
    def _load(cls, identity_file: Path, key_file: Path) -> "NodeIdentity":
        """Load identity from files."""
        with open(identity_file) as f:
            data = json.load(f)
        
        with open(key_file, "rb") as f:
            private_key = f.read()
        
        signing_key = SigningKey(private_key)
        public_key = signing_key.verify_key.encode()
        
        return cls(
            dsid=data["dsid"],
            public_key=public_key,
            private_key=private_key,
            identity_type=data.get("type", "node"),
        )
    
    @classmethod
    def _create(cls, identity_file: Path, key_file: Path) -> "NodeIdentity":
        """Create new identity."""
        # Generate Ed25519 keypair
        signing_key = SigningKey.generate()
        private_key = signing_key.encode()
        public_key = signing_key.verify_key.encode()
        
        # Derive DSID
        dsid = cls._derive_dsid(public_key, "node")
        
        # Save identity
        identity_data = {
            "dsid": dsid,
            "type": "node",
            "public_key": public_key.hex(),
        }
        
        with open(identity_file, "w") as f:
            json.dump(identity_data, f, indent=2)
        
        with open(key_file, "wb") as f:
            f.write(private_key)
        
        # Secure the key file
        key_file.chmod(0o600)
        
        return cls(
            dsid=dsid,
            public_key=public_key,
            private_key=private_key,
            identity_type="node",
        )
    
    @staticmethod
    def _derive_dsid(public_key: bytes, id_type: str) -> str:
        """Derive DSID-P from public key."""
        prefix_map = {
            "user": "dsid-u",
            "org": "dsid-o",
            "agent": "dsid-a",
            "node": "dsid-n",
        }
        prefix = prefix_map.get(id_type, "dsid-n")
        
        # Get fingerprint (first 8 bytes of SHA256)
        fingerprint = hashlib.sha256(public_key).hexdigest()[:16]
        
        # Compute checksum
        checksum_input = f"{prefix}-{fingerprint}"
        checksum = hashlib.sha256(checksum_input.encode()).hexdigest()[:4]
        
        return f"{prefix}-{fingerprint}-{checksum}"
    
    def sign(self, message: bytes) -> bytes:
        """Sign a message."""
        signing_key = SigningKey(self.private_key)
        signed = signing_key.sign(message)
        return signed.signature
    
    def sign_hex(self, message: bytes) -> str:
        """Sign a message and return hex-encoded signature."""
        return self.sign(message).hex()
    
    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify a signature."""
        try:
            verify_key = VerifyKey(public_key)
            verify_key.verify(message, signature)
            return True
        except Exception:
            return False
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "dsid": self.dsid,
            "public_key": self.public_key.hex(),
            "type": self.identity_type,
        }


# DSID API Functions
import uuid
from datetime import datetime

def generate_dsid(entity_type: str, name: str = None, metadata: dict = None) -> dict:
    """Generate a new DSID identity."""
    # Generate keypair
    signing_key = SigningKey.generate()
    public_key = signing_key.verify_key.encode()
    private_key = signing_key.encode()
    
    # Generate entity ID
    entity_id = str(uuid.uuid4())
    
    # Generate DSID using NodeIdentity method
    dsid = NodeIdentity._derive_dsid(public_key, entity_type)
    
    # Generate content hash
    content = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "name": name or f"{entity_type}_generated",
        "metadata": metadata or {},
        "created_at": datetime.now().isoformat()
    }
    content_hash = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    
    return {
        "dsid": dsid,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "public_key": public_key.hex(),
        "content_hash": content_hash,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "anchored": False
    }


def get_identity(dsid: str) -> Optional[dict]:
    """Get DSID identity information (mock implementation)."""
    # Mock implementation - in production this would query the blockchain
    return {
        "dsid": dsid,
        "entity_type": "agent",
        "entity_id": str(uuid.uuid4()),
        "public_key": "mock_public_key",
        "content_hash": hashlib.sha256(f"mock_content_{dsid}".encode()).hexdigest(),
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "anchored": False,
        "anchor_tx_hash": None
    }


def list_identities(entity_type: str = None, limit: int = 50) -> list:
    """List DSID identities (mock implementation)."""
    # Mock implementation - in production this would query the blockchain
    mock_identities = []
    
    for i in range(min(limit, 10)):  # Mock 10 identities max
        dsid = f"dsid:resonant:{entity_type or 'agent'}:{hashlib.sha256(f'mock_{i}'.encode()).hexdigest()[:16]}"
        mock_identities.append({
            "dsid": dsid,
            "entity_type": entity_type or "agent",
            "entity_id": str(uuid.uuid4()),
            "public_key": f"mock_public_key_{i}",
            "content_hash": hashlib.sha256(f"mock_content_{i}".encode()).hexdigest(),
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "anchored": False,
            "anchor_tx_hash": None
        })
    
    return mock_identities
