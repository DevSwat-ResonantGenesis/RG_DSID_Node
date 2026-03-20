"""
Agent Runtime Executor
======================
Executes agents in sandboxed environments with governance.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Context for agent execution."""
    session_id: str
    user_dsid: str
    trust_tier: int
    manifest_hash: str
    sandbox_config: dict = field(default_factory=dict)
    memory_context: Optional[dict] = None


@dataclass
class ExecutionResult:
    """Result of agent execution."""
    success: bool
    output: Any
    execution_hash: str
    tokens_used: int
    duration_ms: int
    governance_decision: str
    audit_log: list = field(default_factory=list)
    error: Optional[str] = None


class AgentRuntime:
    """
    Executes agents in sandboxed environments.
    
    Features:
    - Manifest verification
    - Governance evaluation
    - Sandboxed execution
    - Audit logging
    """
    
    def __init__(
        self,
        chain_client,
        ipfs_gateway: str,
        data_dir: Path,
        max_concurrent: int = 10,
        default_timeout: int = 300,
        sandbox_enabled: bool = True,
    ):
        self.chain_client = chain_client
        self.ipfs_gateway = ipfs_gateway
        self.data_dir = Path(data_dir)
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.sandbox_enabled = sandbox_enabled
        
        self._active = False
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._execution_count = 0
        
        # Components
        self._governance = None
        self._sandbox_pool: dict[str, Any] = {}
        self._manifest_cache: dict[str, dict] = {}
        
        # Execution history (in-memory, last 100 executions)
        self._execution_history: list[dict] = []
        self._max_history = 100
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "cache").mkdir(exist_ok=True)
    
    @property
    def active(self) -> bool:
        return self._active
    
    async def start(self) -> None:
        """Start the runtime."""
        from resonant_node.runtime.governance import GovernanceEngine
        
        self._governance = GovernanceEngine()
        await self._governance.load_policies()
        
        self._active = True
        logger.info("Agent runtime started")
        
        # Keep running
        while self._active:
            await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Stop the runtime."""
        self._active = False
        
        # Terminate all sandboxes
        for sandbox in self._sandbox_pool.values():
            await sandbox.terminate()
        self._sandbox_pool.clear()
        
        logger.info("Agent runtime stopped")
    
    async def execute(
        self,
        manifest_hash: str,
        input_data: dict,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """
        Execute an agent.
        
        Args:
            manifest_hash: Hash of the agent manifest
            input_data: Input data for the agent
            context: Execution context
        
        Returns:
            ExecutionResult with output and audit log.
        """
        start_time = time.time()
        audit_log = []
        
        async with self._semaphore:
            try:
                # 1. Fetch and verify manifest
                manifest = await self._fetch_manifest(manifest_hash)
                audit_log.append({"step": "manifest_fetched", "hash": manifest_hash})
                
                if not manifest:
                    return ExecutionResult(
                        success=False,
                        output=None,
                        execution_hash=self._compute_execution_hash(manifest_hash, input_data),
                        tokens_used=0,
                        duration_ms=int((time.time() - start_time) * 1000),
                        governance_decision="error",
                        audit_log=audit_log,
                        error="Manifest not found",
                    )
                
                # 2. Verify manifest checksum (skip for local agents in dev mode)
                from resonant_node.runtime.local_agents import LOCAL_AGENTS
                is_local = manifest_hash in LOCAL_AGENTS
                
                if not is_local and not self._verify_manifest(manifest, manifest_hash):
                    audit_log.append({"step": "verification_failed"})
                    return ExecutionResult(
                        success=False,
                        output=None,
                        execution_hash=self._compute_execution_hash(manifest_hash, input_data),
                        tokens_used=0,
                        duration_ms=int((time.time() - start_time) * 1000),
                        governance_decision="error",
                        audit_log=audit_log,
                        error="Manifest verification failed",
                    )
                audit_log.append({"step": "manifest_verified", "local": is_local})
                
                # 3. Check governance
                gov_result = await self._governance.evaluate(
                    manifest=manifest,
                    context=context,
                    input_data=input_data,
                )
                audit_log.append({
                    "step": "governance_evaluated",
                    "decision": gov_result.decision,
                    "trust_score": gov_result.trust_score,
                })
                
                if gov_result.decision == "block":
                    return ExecutionResult(
                        success=False,
                        output={"error": gov_result.reason},
                        execution_hash=self._compute_execution_hash(manifest_hash, input_data),
                        tokens_used=0,
                        duration_ms=int((time.time() - start_time) * 1000),
                        governance_decision="block",
                        audit_log=audit_log,
                        error=gov_result.reason,
                    )
                
                # 4. Get or create sandbox
                sandbox = await self._get_sandbox(manifest, context)
                audit_log.append({"step": "sandbox_ready"})
                
                # 5. Load agent code
                agent_code = await self._fetch_agent_code(manifest, manifest_hash)
                if not agent_code:
                    return ExecutionResult(
                        success=False,
                        output=None,
                        execution_hash=self._compute_execution_hash(manifest_hash, input_data),
                        tokens_used=0,
                        duration_ms=int((time.time() - start_time) * 1000),
                        governance_decision="error",
                        audit_log=audit_log,
                        error="Failed to load agent code",
                    )
                audit_log.append({"step": "code_loaded"})
                
                # 6. Execute in sandbox
                exec_result = await sandbox.execute(
                    code=agent_code,
                    entrypoint=manifest["code"]["entrypoint"],
                    input_data=input_data,
                    context=context,
                )
                audit_log.append({
                    "step": "execution_complete",
                    "success": exec_result["success"],
                    "tokens": exec_result.get("tokens_used", 0),
                })
                
                # 7. Compute execution hash
                execution_hash = self._compute_execution_hash(
                    manifest_hash,
                    input_data,
                    exec_result.get("output"),
                )
                
                self._execution_count += 1
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Record in history
                self._record_execution(
                    manifest_hash=manifest_hash,
                    agent_name=manifest.get("agent", {}).get("name", "Unknown Agent"),
                    user_dsid=context.user_dsid,
                    success=exec_result["success"],
                    duration_ms=duration_ms,
                    input_preview=str(input_data)[:100],
                    output_preview=str(exec_result.get("output", ""))[:100],
                    governance_decision=gov_result.decision,
                    execution_hash=execution_hash,
                    error=exec_result.get("error"),
                )
                
                return ExecutionResult(
                    success=exec_result["success"],
                    output=exec_result.get("output"),
                    execution_hash=execution_hash,
                    tokens_used=exec_result.get("tokens_used", 0),
                    duration_ms=duration_ms,
                    governance_decision=gov_result.decision,
                    audit_log=audit_log,
                    error=exec_result.get("error"),
                )
                
            except Exception as e:
                logger.error(f"Execution error: {e}")
                audit_log.append({"step": "error", "message": str(e)})
                return ExecutionResult(
                    success=False,
                    output=None,
                    execution_hash=self._compute_execution_hash(manifest_hash, input_data),
                    tokens_used=0,
                    duration_ms=int((time.time() - start_time) * 1000),
                    governance_decision="error",
                    audit_log=audit_log,
                    error=str(e),
                )
    
    async def _fetch_manifest(self, manifest_hash: str) -> Optional[dict]:
        """Fetch manifest from cache, local registry, or chain."""
        # Check cache
        if manifest_hash in self._manifest_cache:
            return self._manifest_cache[manifest_hash]
        
        # Check local agent registry first (for dev/testing)
        from resonant_node.runtime.local_agents import get_local_manifest
        local_manifest = get_local_manifest(manifest_hash)
        if local_manifest:
            self._manifest_cache[manifest_hash] = local_manifest
            logger.info(f"Loaded local manifest for {manifest_hash[:16]}...")
            return local_manifest
        
        # Fetch from chain
        try:
            agent_record = await self.chain_client.get_agent(manifest_hash)
            if not agent_record:
                return None
            
            # Fetch full manifest from IPFS
            manifest_uri = agent_record.get("manifestUri", "")
            manifest = await self._fetch_from_ipfs(manifest_uri)
            
            if manifest:
                self._manifest_cache[manifest_hash] = manifest
            
            return manifest
        except Exception as e:
            logger.error(f"Failed to fetch manifest: {e}")
            return None
    
    async def _fetch_from_ipfs(self, uri: str) -> Optional[dict]:
        """Fetch JSON from IPFS."""
        import httpx
        
        if uri.startswith("ipfs://"):
            cid = uri[7:]
            url = f"{self.ipfs_gateway}{cid}"
        elif uri.startswith("http"):
            url = uri
        else:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.error(f"IPFS fetch error: {e}")
        
        return None
    
    async def _fetch_agent_code(self, manifest: dict, manifest_hash: str = None) -> Optional[bytes]:
        """Fetch agent code from source."""
        # Try local agent registry first
        if manifest_hash:
            from resonant_node.runtime.local_agents import get_local_agent_code
            local_code = get_local_agent_code(manifest_hash)
            if local_code:
                logger.info(f"Loaded local agent code for {manifest_hash[:16]}...")
                return local_code.encode()
        
        source = manifest.get("code", {}).get("source", {})
        uri = manifest.get("code", {}).get("sourceUri", "") or source.get("uri", "")
        
        # Handle local:// URIs
        if uri.startswith("local://"):
            from resonant_node.runtime.local_agents import get_project_root
            relative_path = uri[8:]  # Remove "local://"
            local_path = get_project_root() / relative_path
            if local_path.exists():
                return local_path.read_bytes()
            logger.warning(f"Local file not found: {local_path}")
            return None
        
        if source.get("type") == "local":
            # Local file (for testing)
            path = Path(uri)
            if path.exists():
                return path.read_bytes()
            return None
        
        # Fetch from IPFS
        import httpx
        
        if uri.startswith("ipfs://"):
            cid = uri[7:]
            url = f"{self.ipfs_gateway}{cid}"
        elif uri.startswith("http"):
            url = uri
        else:
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=60)
                if response.status_code == 200:
                    return response.content
        except Exception as e:
            logger.error(f"Code fetch error: {e}")
        
        return None
    
    def _verify_manifest(self, manifest: dict, expected_hash: str) -> bool:
        """Verify manifest hash matches."""
        from resonant_node.core.crypto import compute_manifest_hash
        
        computed_hash = compute_manifest_hash(manifest)
        return computed_hash == expected_hash
    
    async def _get_sandbox(self, manifest: dict, context: ExecutionContext):
        """Get or create sandbox for agent."""
        from resonant_node.runtime.sandbox import Sandbox, SandboxConfig
        
        sandbox_id = f"{manifest['agent']['id']}:{context.session_id}"
        
        if sandbox_id in self._sandbox_pool:
            return self._sandbox_pool[sandbox_id]
        
        # Build config from manifest
        trust_config = manifest.get("trust", {})
        sandbox_spec = trust_config.get("sandbox", {})
        
        config = SandboxConfig(
            max_memory_mb=sandbox_spec.get("maxMemory", 512),
            max_execution_time=sandbox_spec.get("maxExecutionTime", self.default_timeout),
            max_tokens=sandbox_spec.get("maxTokens", 50000),
            isolated=sandbox_spec.get("isolated", True),
            trust_tier=context.trust_tier,
        )
        
        sandbox = await Sandbox.create(config, self.data_dir / "sandboxes" / sandbox_id)
        self._sandbox_pool[sandbox_id] = sandbox
        
        return sandbox
    
    def _compute_execution_hash(self, *args) -> str:
        """Compute hash of execution for audit."""
        data = "|".join(str(arg) for arg in args)
        return "0x" + hashlib.sha256(data.encode()).hexdigest()
    
    def _record_execution(
        self,
        manifest_hash: str,
        agent_name: str,
        user_dsid: str,
        success: bool,
        duration_ms: int,
        input_preview: str,
        output_preview: str,
        governance_decision: str,
        execution_hash: str,
        error: Optional[str] = None,
    ) -> None:
        """Record execution in history."""
        from datetime import datetime
        
        record = {
            "id": f"exec-{self._execution_count}",
            "manifest_hash": manifest_hash,
            "agent_name": agent_name,
            "user_dsid": user_dsid,
            "success": success,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat(),
            "input_preview": input_preview,
            "output_preview": output_preview,
            "governance_decision": governance_decision,
            "execution_hash": execution_hash,
            "error": error,
            "type": "agent",
        }
        
        self._execution_history.insert(0, record)
        
        # Trim history to max size
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[:self._max_history]
    
    def get_history(self, limit: int = 50) -> list[dict]:
        """Get execution history."""
        return self._execution_history[:limit]
    
    def get_stats(self) -> dict:
        """Get execution statistics."""
        total = len(self._execution_history)
        successful = sum(1 for e in self._execution_history if e["success"])
        failed = total - successful
        avg_duration = (
            sum(e["duration_ms"] for e in self._execution_history) // max(total, 1)
        )
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(successful / max(total, 1) * 100),
            "avg_duration_ms": avg_duration,
        }
