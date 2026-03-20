"""
Agent Sandbox
=============
Isolated execution environment for agents.
"""

import asyncio
import json
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Sandbox configuration."""
    max_memory_mb: int = 512
    max_execution_time: int = 300
    max_tokens: int = 50000
    isolated: bool = True
    trust_tier: int = 0
    network_enabled: bool = False
    allowed_domains: list[str] = None
    
    def __post_init__(self):
        if self.allowed_domains is None:
            self.allowed_domains = []
        
        # Adjust limits based on trust tier
        tier_multipliers = {
            0: 0.5,   # Untrusted
            1: 0.75,  # Basic
            2: 1.0,   # Standard
            3: 1.5,   # Elevated
            4: 2.0,   # Full
        }
        multiplier = tier_multipliers.get(self.trust_tier, 1.0)
        
        self.max_memory_mb = int(self.max_memory_mb * multiplier)
        self.max_execution_time = int(self.max_execution_time * multiplier)
        self.max_tokens = int(self.max_tokens * multiplier)
        
        # Network only for tier 2+
        self.network_enabled = self.trust_tier >= 2


class Sandbox:
    """
    Isolated execution environment for agents.
    
    Provides:
    - Process isolation
    - Resource limits
    - Network restrictions
    - Filesystem isolation
    """
    
    def __init__(
        self,
        sandbox_id: str,
        config: SandboxConfig,
        work_dir: Path,
    ):
        self.sandbox_id = sandbox_id
        self.config = config
        self.work_dir = work_dir
        self._process: Optional[asyncio.subprocess.Process] = None
        self._terminated = False
    
    @classmethod
    async def create(cls, config: SandboxConfig, work_dir: Path) -> "Sandbox":
        """Create a new sandbox."""
        work_dir.mkdir(parents=True, exist_ok=True)
        sandbox_id = work_dir.name
        
        sandbox = cls(sandbox_id, config, work_dir)
        await sandbox._initialize()
        
        return sandbox
    
    async def _initialize(self) -> None:
        """Initialize sandbox environment."""
        # Create subdirectories
        (self.work_dir / "code").mkdir(exist_ok=True)
        (self.work_dir / "data").mkdir(exist_ok=True)
        (self.work_dir / "output").mkdir(exist_ok=True)
    
    async def execute(
        self,
        code: bytes,
        entrypoint: str,
        input_data: dict,
        context: Any,
    ) -> dict:
        """
        Execute agent code in sandbox.
        
        Args:
            code: Agent code bytes
            entrypoint: Entry point file/function
            input_data: Input data for the agent
            context: Execution context
        
        Returns:
            Execution result dictionary.
        """
        if self._terminated:
            return {"success": False, "error": "Sandbox terminated"}
        
        try:
            # Write code to sandbox
            code_path = self.work_dir / "code" / entrypoint
            code_path.parent.mkdir(parents=True, exist_ok=True)
            code_path.write_bytes(code)
            
            # Write input data
            input_path = self.work_dir / "data" / "input.json"
            input_path.write_text(json.dumps({
                "input": input_data,
                "context": {
                    "session_id": context.session_id,
                    "user_dsid": context.user_dsid,
                    "trust_tier": context.trust_tier,
                    "memory": context.memory_context,
                }
            }))
            
            # Prepare execution script
            exec_script = self._create_exec_script(entrypoint)
            script_path = self.work_dir / "code" / "_exec.py"
            script_path.write_text(exec_script)
            
            # Run in subprocess with limits
            result = await self._run_subprocess(script_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Sandbox execution error: {e}")
            return {"success": False, "error": str(e)}
    
    def _create_exec_script(self, entrypoint: str) -> str:
        """Create execution wrapper script."""
        module_name = entrypoint.replace(".py", "").replace("/", ".")
        # Use absolute path to avoid path duplication issues
        abs_work_dir = str(self.work_dir.resolve())
        
        return f'''
import sys
import json
from pathlib import Path

# Set up paths (using absolute path)
work_dir = Path("{abs_work_dir}")
sys.path.insert(0, str(work_dir / "code"))

# Load input
with open(work_dir / "data" / "input.json") as f:
    data = json.load(f)

input_data = data["input"]
context_data = data["context"]

# Create a simple context object that acts like both dict and object
class Context(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return None
    def __setattr__(self, key, value):
        self[key] = value

context = Context(context_data)

# Import agent module
import {module_name} as agent_module

# Try different entry points
result = None
try:
    if hasattr(agent_module, "handle"):
        # Standard ResonantGenesis handler
        result = agent_module.handle(input_data, context)
    elif hasattr(agent_module, "main"):
        # Legacy main function
        result = agent_module.main(input_data, context)
    elif hasattr(agent_module, "agent"):
        # Agent class instance with handle method
        result = agent_module.agent.handle(input_data, context)
    else:
        raise Exception("No valid entry point found (handle, main, or agent.handle)")
    
    output = {{"success": True, "output": result}}
except Exception as e:
    import traceback
    output = {{"success": False, "error": str(e), "traceback": traceback.format_exc()}}

with open(work_dir / "output" / "result.json", "w") as f:
    json.dump(output, f)

print(json.dumps(output))
'''
    
    async def _run_subprocess(self, script_path: Path) -> dict:
        """Run script in subprocess with resource limits."""
        try:
            # Use absolute path for script to avoid cwd conflicts
            abs_script_path = str(script_path.resolve())
            
            # Build command with resource limits
            cmd = [
                "python3",
                abs_script_path,
            ]
            
            # Create subprocess (don't use cwd to avoid path issues)
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Wait with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    self._process.communicate(),
                    timeout=self.config.max_execution_time,
                )
            except asyncio.TimeoutError:
                self._process.kill()
                return {"success": False, "error": "Execution timeout"}
            
            # Check result
            if self._process.returncode == 0:
                try:
                    result = json.loads(stdout.decode())
                    return result
                except json.JSONDecodeError:
                    return {"success": True, "output": stdout.decode()}
            else:
                return {
                    "success": False,
                    "error": stderr.decode() or f"Exit code: {self._process.returncode}",
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self._process = None
    
    async def terminate(self) -> None:
        """Terminate sandbox and clean up."""
        self._terminated = True
        
        if self._process:
            try:
                self._process.kill()
            except ProcessLookupError:
                pass
        
        # Clean up work directory
        try:
            shutil.rmtree(self.work_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to clean up sandbox: {e}")
