"""
Cryptographic Utilities
=======================
DSID-P cryptographic operations.
"""

import hashlib
import json
from typing import Any, Optional

from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import HexEncoder


def generate_keypair() -> tuple[bytes, bytes]:
    """
    Generate Ed25519 keypair.
    
    Returns:
        Tuple of (public_key, private_key) as bytes.
    """
    signing_key = SigningKey.generate()
    private_key = signing_key.encode()
    public_key = signing_key.verify_key.encode()
    return public_key, private_key


def derive_dsid(public_key: bytes, id_type: str = "user") -> str:
    """
    Derive DSID-P from public key.
    
    Args:
        public_key: Ed25519 public key bytes
        id_type: One of "user", "org", "agent", "node"
    
    Returns:
        DSID-P string in format: dsid-{type}-{fingerprint}-{checksum}
    """
    prefix_map = {
        "user": "dsid-u",
        "org": "dsid-o", 
        "agent": "dsid-a",
        "node": "dsid-n",
    }
    prefix = prefix_map.get(id_type, "dsid-u")
    
    # Fingerprint: first 8 bytes (16 hex chars) of SHA256
    fingerprint = hashlib.sha256(public_key).hexdigest()[:16]
    
    # Checksum: first 2 bytes (4 hex chars) of SHA256 of prefix + fingerprint
    checksum_input = f"{prefix}-{fingerprint}"
    checksum = hashlib.sha256(checksum_input.encode()).hexdigest()[:4]
    
    return f"{prefix}-{fingerprint}-{checksum}"


def validate_dsid(dsid: str) -> bool:
    """
    Validate DSID-P format and checksum.
    
    Args:
        dsid: DSID-P string to validate
    
    Returns:
        True if valid, False otherwise.
    """
    import re
    
    pattern = r"^dsid-(u|o|a|n)-([a-f0-9]{16})-([a-f0-9]{4})$"
    match = re.match(pattern, dsid)
    
    if not match:
        return False
    
    type_char, fingerprint, checksum = match.groups()
    
    # Verify checksum
    prefix = f"dsid-{type_char}"
    checksum_input = f"{prefix}-{fingerprint}"
    expected_checksum = hashlib.sha256(checksum_input.encode()).hexdigest()[:4]
    
    return checksum == expected_checksum


def sign_message(private_key: bytes, message: bytes) -> bytes:
    """
    Sign a message with Ed25519.
    
    Args:
        private_key: Ed25519 private key bytes
        message: Message to sign
    
    Returns:
        Signature bytes.
    """
    signing_key = SigningKey(private_key)
    signed = signing_key.sign(message)
    return signed.signature


def verify_signature(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """
    Verify Ed25519 signature.
    
    Args:
        public_key: Ed25519 public key bytes
        message: Original message
        signature: Signature to verify
    
    Returns:
        True if valid, False otherwise.
    """
    try:
        verify_key = VerifyKey(public_key)
        verify_key.verify(message, signature)
        return True
    except Exception:
        return False


def canonicalize(obj: Any) -> str:
    """
    Canonicalize object to deterministic JSON string.
    
    Args:
        obj: Object to canonicalize
    
    Returns:
        Deterministic JSON string with sorted keys.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def compute_hash(data: bytes | str) -> str:
    """
    Compute SHA256 hash.
    
    Args:
        data: Data to hash (bytes or string)
    
    Returns:
        Hex-encoded hash with 0x prefix.
    """
    if isinstance(data, str):
        data = data.encode()
    return "0x" + hashlib.sha256(data).hexdigest()


def compute_manifest_hash(manifest: dict) -> str:
    """
    Compute content-addressable manifest hash.
    
    Args:
        manifest: Manifest dictionary (signature field excluded)
    
    Returns:
        Manifest hash (bytes32 format).
    """
    # Remove signature if present
    manifest_copy = {k: v for k, v in manifest.items() if k != "signature"}
    canonical = canonicalize(manifest_copy)
    return compute_hash(canonical)


def hash_to_bytes32(value: str) -> bytes:
    """
    Convert hex string to bytes32.
    
    Args:
        value: Hex string (with or without 0x prefix)
    
    Returns:
        32-byte value.
    """
    if value.startswith("0x"):
        value = value[2:]
    return bytes.fromhex(value.zfill(64))


def bytes32_to_hex(value: bytes) -> str:
    """
    Convert bytes32 to hex string.
    
    Args:
        value: 32-byte value
    
    Returns:
        Hex string with 0x prefix.
    """
    return "0x" + value.hex()
