"""
Workflow Executor
=================
Executes multi-agent workflows with chaining and data flow.
"""

import asyncio
import json
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Result of a single workflow step."""
    step_id: str
    agent_hash: str
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class WorkflowResult:
    """Result of a complete workflow execution."""
    workflow_id: str
    success: bool
    output: Any
    steps: List[StepResult] = field(default_factory=list)
    total_duration_ms: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class WorkflowExecutor:
    """
    Executes workflows by chaining agent calls.
    
    Features:
    - Sequential step execution
    - Input/output mapping between steps
    - Conditional execution
    - Error handling and retry
    - Timeout support
    """
    
    def __init__(self, runtime):
        """Initialize with agent runtime for executing individual agents."""
        self.runtime = runtime
        self._executions: Dict[str, WorkflowResult] = {}
    
    async def execute(
        self,
        workflow: dict,
        inputs: dict,
        user_dsid: str,
        trust_tier: int = 1,
    ) -> WorkflowResult:
        """
        Execute a workflow.
        
        Args:
            workflow: Workflow definition (following workflow-v1 schema)
            inputs: Input parameters for the workflow
            user_dsid: User's decentralized identifier
            trust_tier: Trust level for execution
            
        Returns:
            WorkflowResult with all step outputs
        """
        workflow_id = workflow.get("workflow", {}).get("id", "unknown")
        started_at = datetime.utcnow().isoformat()
        
        logger.info(f"Starting workflow: {workflow_id}")
        
        result = WorkflowResult(
            workflow_id=workflow_id,
            success=False,
            output=None,
            started_at=started_at,
        )
        
        # Context for variable resolution
        context = {
            "$input": inputs,
            "$steps": {},
        }
        
        steps = workflow.get("steps", [])
        
        try:
            for step_def in steps:
                step_result = await self._execute_step(
                    step_def=step_def,
                    context=context,
                    user_dsid=user_dsid,
                    trust_tier=trust_tier,
                )
                
                result.steps.append(step_result)
                
                # Store step output in context
                step_id = step_def.get("id", f"step-{len(result.steps)}")
                context["$steps"][step_id] = {
                    "output": step_result.output,
                    "success": step_result.success,
                }
                
                # Handle step failure
                if not step_result.success:
                    on_error = step_def.get("onError", "fail")
                    if on_error == "fail":
                        result.error = f"Step {step_id} failed: {step_result.error}"
                        break
                    elif on_error == "skip":
                        logger.warning(f"Step {step_id} failed, skipping remaining steps")
                        break
                    # "continue" - keep going
            
            # Build final output
            if not result.error:
                result.success = True
                result.output = self._build_output(workflow, context)
            
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            result.error = str(e)
        
        result.completed_at = datetime.utcnow().isoformat()
        result.total_duration_ms = sum(s.duration_ms for s in result.steps)
        
        # Store execution
        self._executions[workflow_id] = result
        
        logger.info(f"Workflow {workflow_id} completed: success={result.success}")
        return result
    
    async def _execute_step(
        self,
        step_def: dict,
        context: dict,
        user_dsid: str,
        trust_tier: int,
    ) -> StepResult:
        """Execute a single workflow step."""
        step_id = step_def.get("id", "unknown")
        agent_hash = step_def.get("agent")
        started_at = datetime.utcnow().isoformat()
        
        logger.info(f"Executing step: {step_id} with agent {agent_hash[:16]}...")
        
        # Check condition
        condition = step_def.get("condition")
        if condition:
            if_expr = condition.get("if", "")
            if not self._evaluate_condition(if_expr, context):
                logger.info(f"Step {step_id} skipped due to condition")
                return StepResult(
                    step_id=step_id,
                    agent_hash=agent_hash,
                    success=True,
                    output={"skipped": True, "reason": "condition not met"},
                    started_at=started_at,
                    completed_at=datetime.utcnow().isoformat(),
                )
        
        # Resolve input
        input_data = self._resolve_input(step_def, context)
        
        # Execute with retry
        max_attempts = step_def.get("retry", {}).get("maxAttempts", 1)
        delay_ms = step_def.get("retry", {}).get("delayMs", 1000)
        timeout_ms = step_def.get("timeout", 30000)
        
        last_error = None
        for attempt in range(max_attempts):
            try:
                # Create execution context
                from resonant_node.runtime.executor import ExecutionContext
                exec_context = ExecutionContext(
                    session_id=f"workflow-{step_id}",
                    user_dsid=user_dsid,
                    trust_tier=trust_tier,
                    manifest_hash=agent_hash,
                )
                
                # Execute agent with timeout
                exec_result = await asyncio.wait_for(
                    self.runtime.execute(
                        manifest_hash=agent_hash,
                        input_data=input_data,
                        context=exec_context,
                    ),
                    timeout=timeout_ms / 1000,
                )
                
                return StepResult(
                    step_id=step_id,
                    agent_hash=agent_hash,
                    success=exec_result.success,
                    output=exec_result.output,
                    error=exec_result.error,
                    duration_ms=exec_result.duration_ms,
                    started_at=started_at,
                    completed_at=datetime.utcnow().isoformat(),
                )
                
            except asyncio.TimeoutError:
                last_error = f"Timeout after {timeout_ms}ms"
            except Exception as e:
                last_error = str(e)
            
            if attempt < max_attempts - 1:
                logger.warning(f"Step {step_id} attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(delay_ms / 1000)
        
        return StepResult(
            step_id=step_id,
            agent_hash=agent_hash,
            success=False,
            output=None,
            error=last_error,
            started_at=started_at,
            completed_at=datetime.utcnow().isoformat(),
        )
    
    def _resolve_input(self, step_def: dict, context: dict) -> dict:
        """Resolve step input from static values and mappings."""
        result = {}
        
        # Start with static input
        static_input = step_def.get("input", {})
        result.update(static_input)
        
        # Apply input mappings
        mappings = step_def.get("inputMapping", {})
        for key, expr in mappings.items():
            value = self._resolve_expression(expr, context)
            result[key] = value
        
        return result
    
    def _resolve_expression(self, expr: str, context: dict) -> Any:
        """
        Resolve an expression like '$input.text' or '$steps.step-1.output.result'.
        """
        if not expr.startswith("$"):
            return expr
        
        parts = expr.split(".")
        current = context
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    
    def _evaluate_condition(self, expr: str, context: dict) -> bool:
        """Evaluate a condition expression."""
        if not expr:
            return True
        
        # Simple expression evaluation: $steps.step-1.output.success == true
        match = re.match(r"(\$[a-zA-Z0-9._-]+)\s*(==|!=|>|<|>=|<=)\s*(.+)", expr)
        if not match:
            return True
        
        left_expr, op, right = match.groups()
        left = self._resolve_expression(left_expr, context)
        
        # Parse right side
        right = right.strip()
        if right == "true":
            right = True
        elif right == "false":
            right = False
        elif right.isdigit():
            right = int(right)
        elif right.startswith('"') and right.endswith('"'):
            right = right[1:-1]
        
        # Compare
        if op == "==":
            return left == right
        elif op == "!=":
            return left != right
        elif op == ">":
            return left > right
        elif op == "<":
            return left < right
        elif op == ">=":
            return left >= right
        elif op == "<=":
            return left <= right
        
        return True
    
    def _build_output(self, workflow: dict, context: dict) -> Any:
        """Build final workflow output from output mapping."""
        output_def = workflow.get("output", {})
        mapping = output_def.get("mapping", {})
        
        if not mapping:
            # Return last step's output
            steps = context.get("$steps", {})
            if steps:
                last_step = list(steps.values())[-1]
                return last_step.get("output")
            return None
        
        result = {}
        for key, expr in mapping.items():
            result[key] = self._resolve_expression(expr, context)
        
        return result
    
    def get_execution(self, workflow_id: str) -> Optional[WorkflowResult]:
        """Get a previous workflow execution result."""
        return self._executions.get(workflow_id)
    
    def list_executions(self) -> List[WorkflowResult]:
        """List all workflow executions."""
        return list(self._executions.values())
