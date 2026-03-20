"""Task Planner Agent - Breaks down tasks into steps."""

async def run(inputs: dict) -> dict:
    task = inputs.get("task", "")
    context = inputs.get("context", "")
    
    return {
        "plan": [
            {"step": 1, "action": "Analyze the task requirements", "priority": "high"},
            {"step": 2, "action": "Break down into subtasks", "priority": "high"},
            {"step": 3, "action": "Estimate time for each subtask", "priority": "medium"},
            {"step": 4, "action": "Execute in order of priority", "priority": "medium"},
            {"step": 5, "action": "Review and iterate", "priority": "low"}
        ],
        "task": task,
        "status": "success"
    }
