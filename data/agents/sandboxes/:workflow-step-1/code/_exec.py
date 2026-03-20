
import sys
import json
from pathlib import Path

# Set up paths (using absolute path)
work_dir = Path("/Users/devswat/resonantgenesis_backend/node/data/agents/sandboxes/:workflow-step-1")
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
import main as agent_module

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
    
    output = {"success": True, "output": result}
except Exception as e:
    import traceback
    output = {"success": False, "error": str(e), "traceback": traceback.format_exc()}

with open(work_dir / "output" / "result.json", "w") as f:
    json.dump(output, f)

print(json.dumps(output))
