"""
Hello World Agent
=================
A simple reference agent for the ResonantGenesis network.

This agent demonstrates:
- Basic agent structure
- Input/output handling  
- Memory read/write operations
- Proper response formatting
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class ExecutionContext:
    """Context provided by the runtime"""
    session_id: str
    user_dsid: str
    trust_tier: int
    memory: Optional[Dict[str, Any]] = None


@dataclass  
class AgentResponse:
    """Standard agent response format"""
    success: bool
    output: Any
    memory_updates: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


def main(input_data: Dict[str, Any], context: Optional[ExecutionContext] = None) -> Dict[str, Any]:
    """
    Main entry point for the agent.
    
    Args:
        input_data: The input message/data from the user
        context: Execution context from the runtime (optional)
    
    Returns:
        Agent response dictionary
    """
    # Extract message from input
    message = input_data.get("message", "").lower().strip()
    
    # Initialize response
    response = {
        "success": True,
        "output": None,
        "memory_updates": None,
        "metadata": {
            "agent": "hello-world",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    # Handle different intents
    if not message:
        response["output"] = {
            "type": "greeting",
            "message": "Hello! I'm the Hello World Agent, a reference implementation for the ResonantGenesis network. How can I help you today?",
            "suggestions": [
                "Say 'hello' to get a greeting",
                "Ask 'what is resonantgenesis' for info",
                "Ask 'what can you do' for capabilities"
            ]
        }
    
    elif any(word in message for word in ["hello", "hi", "hey", "greetings"]):
        # Greeting intent
        greeting_count = _get_greeting_count(context)
        greeting_count += 1
        
        response["output"] = {
            "type": "greeting",
            "message": f"Hello! Nice to meet you. This is greeting #{greeting_count} in our conversation.",
            "greeting_count": greeting_count
        }
        response["memory_updates"] = {
            "greeting_count": greeting_count,
            "last_greeting": datetime.utcnow().isoformat()
        }
    
    elif "what is resonantgenesis" in message or "about" in message:
        # Info intent
        response["output"] = {
            "type": "info",
            "message": "ResonantGenesis is an open protocol for autonomous AI agents.",
            "details": {
                "coordination_chain": "Public blockchain for agent identity, manifests, and memory anchors",
                "dsid_p": "Cryptographic identity protocol for users, orgs, and agents",
                "trust_tiers": "Progressive trust system (T0-T4) for agent capabilities",
                "hash_sphere": "Decentralized semantic memory with on-chain integrity"
            }
        }
    
    elif "what can you do" in message or "capabilities" in message or "help" in message:
        # Capabilities intent
        response["output"] = {
            "type": "capabilities",
            "message": "I'm a simple reference agent. Here's what I can do:",
            "capabilities": [
                "Respond to greetings",
                "Provide information about ResonantGenesis",
                "Demonstrate memory read/write",
                "Show proper agent response format"
            ],
            "trust_tier": context.trust_tier if context else 1,
            "tools": ["memory.read", "memory.write"]
        }
    
    elif "remember" in message:
        # Memory demo
        # Extract what to remember
        to_remember = message.replace("remember", "").strip()
        if to_remember:
            response["output"] = {
                "type": "memory",
                "message": f"I'll remember that: '{to_remember}'",
                "stored": True
            }
            response["memory_updates"] = {
                "user_note": to_remember,
                "noted_at": datetime.utcnow().isoformat()
            }
        else:
            response["output"] = {
                "type": "memory",
                "message": "What would you like me to remember? Say 'remember <something>'",
                "stored": False
            }
    
    elif "recall" in message or "what do you remember" in message:
        # Memory recall demo
        memory = context.memory if context else {}
        user_note = memory.get("user_note")
        greeting_count = memory.get("greeting_count", 0)
        
        response["output"] = {
            "type": "recall",
            "message": "Here's what I remember from our conversation:",
            "memory": {
                "user_note": user_note or "Nothing stored yet",
                "greeting_count": greeting_count,
                "last_greeting": memory.get("last_greeting")
            }
        }
    
    else:
        # Default response
        response["output"] = {
            "type": "default",
            "message": f"I received your message: '{input_data.get('message', '')}'",
            "hint": "Try saying 'hello', 'what is resonantgenesis', or 'what can you do'"
        }
    
    return response


def _get_greeting_count(context: Optional[ExecutionContext]) -> int:
    """Get greeting count from memory"""
    if context and context.memory:
        return context.memory.get("greeting_count", 0)
    return 0


# For direct execution / testing
if __name__ == "__main__":
    import sys
    
    # Test with sample inputs
    test_inputs = [
        {"message": ""},
        {"message": "hello"},
        {"message": "what is resonantgenesis"},
        {"message": "what can you do"},
        {"message": "remember I like pizza"},
        {"message": "what do you remember"}
    ]
    
    print("=" * 60)
    print("Hello World Agent - Test Run")
    print("=" * 60)
    
    context = ExecutionContext(
        session_id="test-session",
        user_dsid="dsid-u-test12345678-abcd",
        trust_tier=1,
        memory={}
    )
    
    for test_input in test_inputs:
        print(f"\n> Input: {test_input}")
        result = main(test_input, context)
        print(f"< Output: {json.dumps(result['output'], indent=2)}")
        
        # Update context memory for next iteration
        if result.get("memory_updates"):
            context.memory.update(result["memory_updates"])
    
    print("\n" + "=" * 60)
    print("Test complete!")
