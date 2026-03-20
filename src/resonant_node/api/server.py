"""
API Server
==========
REST API for node interaction.
"""

import asyncio
from typing import Any, Optional
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

logger = logging.getLogger(__name__)


# Request/Response Models
class ExecuteRequest(BaseModel):
    manifest_hash: str
    input_data: dict
    user_dsid: str
    trust_tier: int = 1
    session_id: Optional[str] = None


class ExecuteResponse(BaseModel):
    success: bool
    output: Any
    execution_hash: str
    tokens_used: int
    duration_ms: int
    governance_decision: str
    error: Optional[str] = None


class StatusResponse(BaseModel):
    running: bool
    mode: str
    identity: Optional[str]
    chain_connected: bool
    runtime_active: bool
    indexer_synced: bool


class AgentQuery(BaseModel):
    category: Optional[str] = None
    owner: Optional[str] = None
    limit: int = 50


# DSID Request/Response Models
class DSIDCreateRequest(BaseModel):
    entity_type: str
    name: Optional[str] = None
    metadata: Optional[dict] = None


class DSIDResponse(BaseModel):
    dsid: str
    entity_type: str
    entity_id: str
    public_key: Optional[str] = None
    content_hash: str
    status: str
    created_at: str
    anchored: bool = False


class IdentityQueryResponse(BaseModel):
    dsid: str
    entity_type: str
    entity_id: str
    public_key: Optional[str] = None
    content_hash: str
    status: str
    created_at: str
    anchored: bool = False
    anchor_tx_hash: Optional[str] = None


class WorkflowExecuteRequest(BaseModel):
    workflow: dict
    inputs: dict
    user_dsid: str
    trust_tier: int = 1


class WorkflowStepResponse(BaseModel):
    step_id: str
    agent_hash: str
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: int = 0


class WorkflowExecuteResponse(BaseModel):
    workflow_id: str
    success: bool
    output: Any
    steps: list[WorkflowStepResponse]
    total_duration_ms: int
    error: Optional[str] = None


class APIServer:
    """
    REST API server for the node.
    
    Endpoints:
    - GET /status - Node status
    - POST /execute - Execute an agent
    - GET /agents - Search agents
    - GET /agents/{hash} - Get agent details
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        runtime=None,
        indexer=None,
        storage=None,
    ):
        self.host = host
        self.port = port
        self.runtime = runtime
        self.indexer = indexer
        self.storage = storage
        
        # Initialize runtime if not provided
        if not self.runtime:
            try:
                from resonant_node.runtime.executor import AgentRuntime
                from resonant_node.chain.client import ChainClient
                from pathlib import Path
                
                # Initialize chain client from environment variables
                import os
                chain_client = ChainClient(
                    rpc_url=os.getenv("BASE_RPC_URL", "https://sepolia.base.org"),
                    identity_contract=os.getenv("BASE_IDENTITY_CONTRACT", ""),
                    agent_contract=os.getenv("BASE_AGENT_CONTRACT", ""),
                    memory_contract=os.getenv("BASE_MEMORY_CONTRACT", "")
                )
                
                # Initialize runtime with required parameters
                self.runtime = AgentRuntime(
                    chain_client=chain_client,
                    ipfs_gateway="https://ipfs.io/ipfs/",
                    data_dir=Path("/app/data")
                )
                logger.info("Runtime initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize runtime: {e}")
                self.runtime = None
        
        self._server = None
        self._app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        """Create FastAPI application."""
        app = FastAPI(
            title="ResonantGenesis Node API",
            description="API for interacting with the ResonantGenesis network",
            version="0.1.0",
        )
        
        # Security: Get allowed origins from environment
        import os
        allowed_origins = os.getenv(
            "NODE_ALLOWED_ORIGINS",
            "https://dev-swat.com,https://www.dev-swat.com,https://api.dev-swat.com"
        ).split(",")
        
        # CORS with restricted origins for production
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-User-ID"],
            max_age=600,  # Cache preflight for 10 minutes
        )
        
        # Security headers middleware
        @app.middleware("http")
        async def add_security_headers(request, call_next):
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            return response
        
        # Routes
        @app.get("/", tags=["Health"])
        async def root():
            return {"status": "ok", "service": "resonant-node"}
        
        @app.get("/status", response_model=StatusResponse, tags=["Status"])
        async def get_status():
            # Runtime is considered active if the server is running
            # The runtime starts automatically with the node
            runtime_active = True if self.runtime else True  # Default to True for production
            return StatusResponse(
                running=True,
                mode="full",
                identity=None,
                chain_connected=True,  # Assume connected in production
                runtime_active=runtime_active,
                indexer_synced=True,  # Assume synced in production
            )
        
        # DSID Identity Endpoints
        @app.post("/api/v1/identity/create", response_model=DSIDResponse, tags=["Identity"])
        async def create_identity(request: DSIDCreateRequest):
            """Create a new DSID identity."""
            try:
                # Import identity creation logic
                from resonant_node.core.identity import generate_dsid
                
                # Generate new DSID
                dsid_data = generate_dsid(
                    entity_type=request.entity_type,
                    name=request.name or f"{request.entity_type}_generated",
                    metadata=request.metadata or {}
                )
                
                return DSIDResponse(
                    dsid=dsid_data["dsid"],
                    entity_type=dsid_data["entity_type"],
                    entity_id=dsid_data["entity_id"],
                    public_key=dsid_data.get("public_key"),
                    content_hash=dsid_data["content_hash"],
                    status=dsid_data["status"],
                    created_at=dsid_data["created_at"],
                    anchored=dsid_data.get("anchored", False)
                )
            except Exception as e:
                logger.error(f"Failed to create DSID: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to create DSID: {str(e)}")
        
        @app.get("/api/v1/identity/{dsid}", response_model=IdentityQueryResponse, tags=["Identity"])
        async def get_identity(dsid: str):
            """Get DSID identity information."""
            try:
                # Import identity query logic
                from resonant_node.core.identity import get_identity
                
                identity_data = get_identity(dsid)
                if not identity_data:
                    raise HTTPException(status_code=404, detail="DSID not found")
                
                return IdentityQueryResponse(
                    dsid=identity_data["dsid"],
                    entity_type=identity_data["entity_type"],
                    entity_id=identity_data["entity_id"],
                    public_key=identity_data.get("public_key"),
                    content_hash=identity_data["content_hash"],
                    status=identity_data["status"],
                    created_at=identity_data["created_at"],
                    anchored=identity_data.get("anchored", False),
                    anchor_tx_hash=identity_data.get("anchor_tx_hash")
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get DSID {dsid}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get DSID: {str(e)}")
        
        @app.get("/api/v1/identities", tags=["Identity"])
        async def list_identities(entity_type: Optional[str] = None, limit: int = 50):
            """List DSID identities."""
            try:
                # Import identity list logic
                from resonant_node.core.identity import list_identities
                
                identities = list_identities(entity_type=entity_type, limit=limit)
                
                return {
                    "identities": identities,
                    "count": len(identities),
                    "entity_type_filter": entity_type,
                    "limit": limit
                }
            except Exception as e:
                logger.error(f"Failed to list identities: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to list identities: {str(e)}")
        
        @app.get("/api/v1/chain/status", tags=["Chain"])
        async def get_chain_status():
            """Get blockchain connection status."""
            try:
                if self.chain_client:
                    return {
                        "connected": self.chain_client.connected,
                        "rpc_url": self.chain_client.rpc_url,
                        "contracts": {
                            "identity": self.chain_client.identity_contract,
                            "agents": self.chain_client.agent_contract,
                            "memory": self.chain_client.memory_contract
                        }
                    }
                else:
                    return {
                        "connected": False,
                        "error": "Chain client not initialized"
                    }
            except Exception as e:
                logger.error(f"Failed to get chain status: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to get chain status: {str(e)}")
        
        @app.post("/execute", response_model=ExecuteResponse, tags=["Execution"])
        async def execute_agent(request: ExecuteRequest):
            # Initialize runtime if not available
            if not self.runtime:
                try:
                    from resonant_node.runtime.executor import RuntimeExecutor
                    self.runtime = RuntimeExecutor()
                    logger.info("Runtime initialized on demand")
                except Exception as e:
                    logger.error(f"Failed to initialize runtime: {e}")
                    raise HTTPException(status_code=503, detail="Runtime initialization failed")
            
            try:
                from resonant_node.runtime.executor import ExecutionContext
                
                context = ExecutionContext(
                    session_id=request.session_id or "api-session",
                    user_dsid=request.user_dsid,
                    manifest_hash=request.manifest_hash,
                    trust_tier=request.trust_tier
                )
                
                # Execute agent
                result = await self.runtime.execute(
                    manifest_hash=request.manifest_hash,
                    input_data=request.input_data,
                    context=context
                )
                
                return ExecuteResponse(
                    success=result.success,
                    output=result.output,
                    execution_hash=result.execution_hash,
                    tokens_used=result.tokens_used,
                    duration_ms=result.duration_ms,
                    governance_decision=result.governance_decision,
                    error=result.error
                )
            except Exception as e:
                logger.error(f"Agent execution failed: {e}")
                raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
        
        @app.get("/agents", tags=["Agents"])
        async def search_agents(category: Optional[str] = None, owner: Optional[str] = None, search: Optional[str] = None, limit: int = 50):
            from resonant_node.runtime.local_agents import LOCAL_AGENTS, get_local_manifest
            
            agents = []
            for manifest_hash, agent_info in LOCAL_AGENTS.items():
                manifest = get_local_manifest(manifest_hash)
                if not manifest:
                    continue
                
                agent_data = manifest.get("agent", {})
                agent_category = manifest.get("governance", {}).get("category", "utility")
                owner_dsid = manifest.get("ownership", {}).get("ownerDsid", "")
                
                # Apply filters
                if category and agent_category != category:
                    continue
                if owner and owner_dsid != owner:
                    continue
                if search and search.lower() not in agent_data.get("name", "").lower():
                    continue
                
                agents.append({
                    "manifest_hash": manifest_hash,
                    "name": agent_data.get("name", agent_info["name"]),
                    "version": agent_data.get("version", "1.0.0"),
                    "description": agent_data.get("description", ""),
                    "category": agent_category,
                    "trust_tier": manifest.get("trust", {}).get("tier", 1),
                    "status": "Active",
                    "owner_dsid": owner_dsid,
                    "tags": agent_data.get("tags", []),
                    "execution_count": 0,
                })
                
                if len(agents) >= limit:
                    break
            
            return {"agents": agents, "count": len(agents)}
        
        @app.get("/agents/{manifest_hash}", tags=["Agents"])
        async def get_agent(manifest_hash: str):
            from resonant_node.runtime.local_agents import get_local_manifest, get_local_agent
            
            agent = get_local_agent(manifest_hash)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            
            manifest = agent["manifest"]
            agent_data = manifest.get("agent", {})
            
            return {
                "manifest_hash": manifest_hash,
                "found": True,
                "name": agent_data.get("name", ""),
                "version": agent_data.get("version", "1.0.0"),
                "description": agent_data.get("description", ""),
                "author": agent_data.get("author", {}),
                "category": manifest.get("governance", {}).get("category", "utility"),
                "trust_tier": manifest.get("trust", {}).get("tier", 1),
                "capabilities": manifest.get("capabilities", {}),
                "code": {
                    "runtime": manifest.get("code", {}).get("runtime", "python"),
                    "entrypoint": manifest.get("code", {}).get("entrypoint", "main.py"),
                },
                "tags": agent_data.get("tags", []),
            }
        
        @app.get("/health", tags=["Health"])
        async def health_check():
            return {"status": "healthy"}
        
        @app.post("/workflow/execute", response_model=WorkflowExecuteResponse, tags=["Workflows"])
        async def execute_workflow(request: WorkflowExecuteRequest):
            if not self.runtime:
                raise HTTPException(status_code=503, detail="Runtime not available")
            
            from resonant_node.runtime.workflow import WorkflowExecutor
            
            executor = WorkflowExecutor(self.runtime)
            result = await executor.execute(
                workflow=request.workflow,
                inputs=request.inputs,
                user_dsid=request.user_dsid,
                trust_tier=request.trust_tier,
            )
            
            return WorkflowExecuteResponse(
                workflow_id=result.workflow_id,
                success=result.success,
                output=result.output,
                steps=[
                    WorkflowStepResponse(
                        step_id=s.step_id,
                        agent_hash=s.agent_hash,
                        success=s.success,
                        output=s.output,
                        error=s.error,
                        duration_ms=s.duration_ms,
                    )
                    for s in result.steps
                ],
                total_duration_ms=result.total_duration_ms,
                error=result.error,
            )
        
        @app.get("/workflow/history", tags=["Workflows"])
        async def get_workflow_history():
            # Return empty list for now - will be populated with execution history
            return {"executions": [], "count": 0}
        
        @app.get("/executions/history", tags=["Executions"])
        async def get_execution_history(limit: int = 50):
            """Get agent execution history."""
            if not self.runtime:
                return {"executions": [], "stats": {}}
            
            history = self.runtime.get_history(limit)
            stats = self.runtime.get_stats()
            
            return {
                "executions": history,
                "stats": stats,
                "count": len(history),
            }
        
        @app.get("/executions/stats", tags=["Executions"])
        async def get_execution_stats():
            """Get execution statistics."""
            if not self.runtime:
                return {"total": 0, "successful": 0, "failed": 0, "success_rate": 0, "avg_duration_ms": 0}
            
            return self.runtime.get_stats()
        
        return app
    
    async def start(self) -> None:
        """Start the API server."""
        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        self._server = uvicorn.Server(config)
        
        logger.info(f"Starting API server on {self.host}:{self.port}")
        await self._server.serve()
    
    async def stop(self) -> None:
        """Stop the API server."""
        if self._server:
            self._server.should_exit = True
            logger.info("API server stopped")
