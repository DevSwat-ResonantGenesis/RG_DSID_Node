"""Data Summarizer Agent - Summarizes text and data."""

async def run(inputs: dict) -> dict:
    data = inputs.get("data", "")
    max_length = inputs.get("max_length", 500)
    
    words = data.split()
    summary = " ".join(words[:min(len(words), max_length // 5)])
    
    return {
        "summary": summary + "..." if len(words) > max_length // 5 else summary,
        "original_length": len(data),
        "summary_length": len(summary),
        "status": "success"
    }
