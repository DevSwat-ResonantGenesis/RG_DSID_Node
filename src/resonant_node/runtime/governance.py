"""
Governance Engine
=================
Evaluates agent actions against policies.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class GovernanceDecision(Enum):
    """Governance decision types."""
    PASS = "pass"
    FLAG = "flag"
    BLOCK = "block"


@dataclass
class Policy:
    """Governance policy definition."""
    id: str
    name: str
    priority: int
    conditions: dict
    action: GovernanceDecision
    description: str = ""


@dataclass
class GovernanceResult:
    """Result of governance evaluation."""
    decision: str
    reason: Optional[str]
    policies_evaluated: list[str]
    trust_score: float
    flags: list[str] = field(default_factory=list)


class GovernanceEngine:
    """
    Evaluates agent actions against policies.
    
    Features:
    - Policy-based evaluation
    - Trust tier enforcement
    - Tool permission checking
    - Rate limiting
    """
    
    def __init__(self):
        self.policies: list[Policy] = []
        self.trust_thresholds = {
            0: 0.9,   # Untrusted: very strict
            1: 0.7,   # Basic
            2: 0.5,   # Standard
            3: 0.3,   # Elevated
            4: 0.1,   # Full: permissive
        }
        self._execution_counts: dict[str, int] = {}
    
    async def load_policies(self, policies_path: Optional[str] = None) -> None:
        """Load governance policies."""
        # Default policies
        self.policies = [
            Policy(
                id="p001",
                name="block_dangerous_tools",
                priority=100,
                conditions={
                    "tools": ["code.execute", "filesystem.write", "shell.execute"],
                    "trust_tier_below": 2,
                },
                action=GovernanceDecision.BLOCK,
                description="Block dangerous tools for untrusted agents",
            ),
            Policy(
                id="p002",
                name="flag_network_access",
                priority=50,
                conditions={
                    "tools": ["network.http", "network.websocket"],
                    "trust_tier_below": 3,
                },
                action=GovernanceDecision.FLAG,
                description="Flag network access for lower trust tiers",
            ),
            Policy(
                id="p003",
                name="rate_limit_spawning",
                priority=75,
                conditions={
                    "tools": ["agent.spawn"],
                    "rate_limit": {"max": 50, "window": 60},  # Increased for dev (was 5)
                },
                action=GovernanceDecision.BLOCK,
                description="Rate limit agent spawning",
            ),
            Policy(
                id="p004",
                name="block_memory_cross_access",
                priority=90,
                conditions={
                    "memory_scope": "global",
                    "trust_tier_below": 4,
                },
                action=GovernanceDecision.BLOCK,
                description="Block global memory access for non-trusted agents",
            ),
            Policy(
                id="p005",
                name="flag_high_token_usage",
                priority=30,
                conditions={
                    "token_threshold": 10000,
                },
                action=GovernanceDecision.FLAG,
                description="Flag high token usage requests",
            ),
        ]
        
        logger.info(f"Loaded {len(self.policies)} governance policies")
    
    async def evaluate(
        self,
        manifest: dict,
        context: Any,
        input_data: dict,
    ) -> GovernanceResult:
        """
        Evaluate execution against policies.
        
        Args:
            manifest: Agent manifest
            context: Execution context
            input_data: Input data for the agent
        
        Returns:
            GovernanceResult with decision and details.
        """
        evaluated_policies = []
        flags = []
        block_reason = None
        
        # Get agent capabilities
        capabilities = manifest.get("capabilities", {})
        tools_list = capabilities.get("tools", [])
        # Handle both formats: list of strings or list of dicts with "tool" key
        if tools_list and isinstance(tools_list[0], str):
            requested_tools = tools_list
        else:
            requested_tools = [t["tool"] if isinstance(t, dict) else t for t in tools_list]
        memory_scope = capabilities.get("memory", {}).get("scope", "self")
        trust_tier = context.trust_tier
        
        # Evaluate each policy
        for policy in sorted(self.policies, key=lambda p: -p.priority):
            result = self._evaluate_policy(
                policy=policy,
                requested_tools=requested_tools,
                memory_scope=memory_scope,
                trust_tier=trust_tier,
                context=context,
                input_data=input_data,
            )
            
            evaluated_policies.append(policy.id)
            
            if result["triggered"]:
                if policy.action == GovernanceDecision.BLOCK:
                    block_reason = f"Policy {policy.name}: {result['reason']}"
                    break
                elif policy.action == GovernanceDecision.FLAG:
                    flags.append(f"Policy {policy.name}: {result['reason']}")
        
        # Calculate trust score
        trust_score = self._calculate_trust_score(manifest, context)
        threshold = self.trust_thresholds.get(trust_tier, 0.5)
        
        # Determine final decision
        if block_reason:
            return GovernanceResult(
                decision="block",
                reason=block_reason,
                policies_evaluated=evaluated_policies,
                trust_score=trust_score,
                flags=flags,
            )
        
        if trust_score < threshold:
            return GovernanceResult(
                decision="flag",
                reason=f"Trust score {trust_score:.2f} below threshold {threshold}",
                policies_evaluated=evaluated_policies,
                trust_score=trust_score,
                flags=flags,
            )
        
        decision = "flag" if flags else "pass"
        
        return GovernanceResult(
            decision=decision,
            reason="; ".join(flags) if flags else None,
            policies_evaluated=evaluated_policies,
            trust_score=trust_score,
            flags=flags,
        )
    
    def _evaluate_policy(
        self,
        policy: Policy,
        requested_tools: list[str],
        memory_scope: str,
        trust_tier: int,
        context: Any,
        input_data: dict,
    ) -> dict:
        """Evaluate a single policy."""
        conditions = policy.conditions
        
        # Check tool conditions
        if "tools" in conditions:
            matching_tools = set(conditions["tools"]) & set(requested_tools)
            if matching_tools:
                if "trust_tier_below" in conditions:
                    if trust_tier < conditions["trust_tier_below"]:
                        return {
                            "triggered": True,
                            "reason": f"Tools {matching_tools} require trust tier >= {conditions['trust_tier_below']}",
                        }
        
        # Check memory scope
        if "memory_scope" in conditions:
            if memory_scope == conditions["memory_scope"]:
                if "trust_tier_below" in conditions:
                    if trust_tier < conditions["trust_tier_below"]:
                        return {
                            "triggered": True,
                            "reason": f"Memory scope '{memory_scope}' requires trust tier >= {conditions['trust_tier_below']}",
                        }
        
        # Check rate limits
        if "rate_limit" in conditions:
            rate_config = conditions["rate_limit"]
            key = f"{context.user_dsid}:{policy.id}"
            count = self._execution_counts.get(key, 0)
            
            if count >= rate_config["max"]:
                return {
                    "triggered": True,
                    "reason": f"Rate limit exceeded ({count}/{rate_config['max']})",
                }
            
            # Increment counter
            self._execution_counts[key] = count + 1
        
        # Check token threshold
        if "token_threshold" in conditions:
            # Estimate token usage from input
            input_str = str(input_data)
            estimated_tokens = len(input_str) // 4  # Rough estimate
            
            if estimated_tokens > conditions["token_threshold"]:
                return {
                    "triggered": True,
                    "reason": f"Estimated tokens ({estimated_tokens}) exceeds threshold",
                }
        
        return {"triggered": False, "reason": None}
    
    def _calculate_trust_score(self, manifest: dict, context: Any) -> float:
        """Calculate trust score for execution."""
        score = 1.0
        
        # Reduce for high-risk tools
        high_risk_tools = ["code.execute", "agent.spawn", "filesystem.write", "shell.execute"]
        tools_list = manifest.get("capabilities", {}).get("tools", [])
        # Handle both string list and dict list formats
        if tools_list and isinstance(tools_list[0], str):
            requested_tools = tools_list
        else:
            requested_tools = [t["tool"] if isinstance(t, dict) else t for t in tools_list]
        
        for tool in requested_tools:
            if tool in high_risk_tools:
                score -= 0.15
        
        # Reduce for network access
        network_config = manifest.get("capabilities", {}).get("network", {})
        if network_config.get("allowedDomains"):
            score -= 0.1
        
        # Boost for audit level
        audit_level = manifest.get("trust", {}).get("auditLevel", "none")
        audit_boosts = {"none": 0, "basic": 0.1, "full": 0.2, "compliance": 0.3}
        score += audit_boosts.get(audit_level, 0)
        
        # Boost for sandbox isolation
        if manifest.get("trust", {}).get("sandbox", {}).get("isolated"):
            score += 0.1
        
        # Consider trust tier
        score += context.trust_tier * 0.05
        
        return max(0.0, min(1.0, score))
