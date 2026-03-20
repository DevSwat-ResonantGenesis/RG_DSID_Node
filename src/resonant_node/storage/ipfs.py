"""
Storage Manager
===============
Manages content storage via IPFS.
"""

import asyncio
import hashlib
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Manages content storage.
    
    Provides:
    - IPFS gateway access
    - Local caching
    - Content verification
    """
    
    def __init__(
        self,
        ipfs_gateway: str,
        ipfs_api: Optional[str] = None,
        data_dir: Path = None,
    ):
        self.ipfs_gateway = ipfs_gateway.rstrip("/")
        self.ipfs_api = ipfs_api
        self.data_dir = Path(data_dir) if data_dir else Path("./data/storage")
        
        self._running = False
        
        # Ensure directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "cache").mkdir(exist_ok=True)
    
    async def start(self) -> None:
        """Start the storage manager."""
        self._running = True
        logger.info("Storage manager started")
        
        while self._running:
            await asyncio.sleep(60)  # Maintenance loop
    
    async def stop(self) -> None:
        """Stop the storage manager."""
        self._running = False
        logger.info("Storage manager stopped")
    
    async def fetch(self, uri: str) -> Optional[bytes]:
        """
        Fetch content from URI.
        
        Args:
            uri: Content URI (ipfs://, http://, or local path)
        
        Returns:
            Content bytes or None if not found.
        """
        # Check cache first
        cache_key = self._cache_key(uri)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached
        
        # Fetch based on URI scheme
        content = None
        
        if uri.startswith("ipfs://"):
            content = await self._fetch_ipfs(uri[7:])
        elif uri.startswith("http"):
            content = await self._fetch_http(uri)
        elif uri.startswith("./") or uri.startswith("/"):
            content = await self._fetch_local(uri)
        
        # Cache if found
        if content:
            await self._cache(cache_key, content)
        
        return content
    
    async def _fetch_ipfs(self, cid: str) -> Optional[bytes]:
        """Fetch from IPFS."""
        import httpx
        
        url = f"{self.ipfs_gateway}/{cid}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=60)
                if response.status_code == 200:
                    return response.content
        except Exception as e:
            logger.error(f"IPFS fetch error: {e}")
        
        return None
    
    async def _fetch_http(self, url: str) -> Optional[bytes]:
        """Fetch from HTTP."""
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=60)
                if response.status_code == 200:
                    return response.content
        except Exception as e:
            logger.error(f"HTTP fetch error: {e}")
        
        return None
    
    async def _fetch_local(self, path: str) -> Optional[bytes]:
        """Fetch from local filesystem."""
        try:
            p = Path(path)
            if p.exists():
                return p.read_bytes()
        except Exception as e:
            logger.error(f"Local fetch error: {e}")
        
        return None
    
    async def upload(self, content: bytes) -> Optional[str]:
        """
        Upload content to IPFS.
        
        Args:
            content: Content bytes to upload
        
        Returns:
            IPFS CID or None if upload failed.
        """
        if not self.ipfs_api:
            logger.warning("IPFS API not configured")
            return None
        
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ipfs_api}/api/v0/add",
                    files={"file": content},
                    timeout=120,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("Hash")
        except Exception as e:
            logger.error(f"IPFS upload error: {e}")
        
        return None
    
    def _cache_key(self, uri: str) -> str:
        """Generate cache key from URI."""
        return hashlib.sha256(uri.encode()).hexdigest()[:32]
    
    async def _get_cached(self, key: str) -> Optional[bytes]:
        """Get cached content."""
        cache_path = self.data_dir / "cache" / key
        if cache_path.exists():
            return cache_path.read_bytes()
        return None
    
    async def _cache(self, key: str, content: bytes) -> None:
        """Cache content."""
        cache_path = self.data_dir / "cache" / key
        cache_path.write_bytes(content)
