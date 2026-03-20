"""
Data Summarizer Agent
=====================
Summarizes text, lists, and structured data into concise formats.
"""

from typing import Any, Dict
from datetime import datetime
import re


def handle(input_data: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Summarize input data into a concise format.
    
    Supported input types:
    - text: Summarize long text
    - list: Summarize a list of items
    - data: Summarize structured data/dict
    """
    data_type = input_data.get("type", "auto")
    content = input_data.get("content", input_data.get("text", input_data.get("data")))
    max_length = input_data.get("max_length", 200)
    
    if not content:
        return {
            "success": False,
            "error": "No content provided. Use 'content', 'text', or 'data' field.",
            "usage": {
                "text": "Provide text to summarize",
                "list": "Provide a list of items",
                "data": "Provide structured data (dict)"
            }
        }
    
    # Auto-detect type
    if data_type == "auto":
        if isinstance(content, str):
            data_type = "text"
        elif isinstance(content, list):
            data_type = "list"
        elif isinstance(content, dict):
            data_type = "data"
        else:
            data_type = "text"
            content = str(content)
    
    # Summarize based on type
    if data_type == "text":
        summary = summarize_text(content, max_length)
    elif data_type == "list":
        summary = summarize_list(content, max_length)
    elif data_type == "data":
        summary = summarize_data(content, max_length)
    else:
        summary = summarize_text(str(content), max_length)
    
    return {
        "success": True,
        "output": {
            "type": "summary",
            "input_type": data_type,
            "original_length": len(str(content)),
            "summary_length": len(summary["text"]),
            "compression_ratio": f"{(1 - len(summary['text']) / max(len(str(content)), 1)) * 100:.1f}%",
            "summary": summary["text"],
            "key_points": summary.get("key_points", []),
            "statistics": summary.get("stats", {}),
        },
        "metadata": {
            "agent": "data-summarizer",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }
    }


def summarize_text(text: str, max_length: int) -> Dict[str, Any]:
    """Summarize plain text."""
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    # Calculate word frequencies
    words = re.findall(r'\b\w+\b', text.lower())
    word_freq = {}
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                  'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                  'as', 'into', 'through', 'during', 'before', 'after', 'and',
                  'but', 'or', 'nor', 'so', 'yet', 'both', 'either', 'neither',
                  'not', 'only', 'own', 'same', 'than', 'too', 'very', 'just',
                  'that', 'this', 'these', 'those', 'it', 'its'}
    
    for word in words:
        if word not in stop_words and len(word) > 2:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Score sentences
    sentence_scores = []
    for sent in sentences:
        score = sum(word_freq.get(w.lower(), 0) for w in re.findall(r'\b\w+\b', sent))
        sentence_scores.append((sent, score))
    
    # Sort by score and take top sentences
    sentence_scores.sort(key=lambda x: -x[1])
    
    summary_sentences = []
    current_length = 0
    for sent, score in sentence_scores:
        if current_length + len(sent) <= max_length:
            summary_sentences.append(sent)
            current_length += len(sent) + 1
    
    # Reorder by original position
    original_order = {sent: i for i, sent in enumerate(sentences)}
    summary_sentences.sort(key=lambda s: original_order.get(s, 999))
    
    # Extract key points (top keywords)
    top_words = sorted(word_freq.items(), key=lambda x: -x[1])[:5]
    key_points = [word for word, freq in top_words]
    
    return {
        "text": ' '.join(summary_sentences) if summary_sentences else text[:max_length],
        "key_points": key_points,
        "stats": {
            "total_sentences": len(sentences),
            "summary_sentences": len(summary_sentences),
            "total_words": len(words),
            "unique_words": len(word_freq)
        }
    }


def summarize_list(items: list, max_length: int) -> Dict[str, Any]:
    """Summarize a list of items."""
    if not items:
        return {"text": "Empty list", "key_points": [], "stats": {"count": 0}}
    
    # Categorize items
    item_types = {}
    for item in items:
        t = type(item).__name__
        item_types[t] = item_types.get(t, 0) + 1
    
    # Create summary
    count = len(items)
    
    if count <= 5:
        summary = f"List of {count} items: {', '.join(str(i) for i in items)}"
    else:
        first_items = ', '.join(str(i) for i in items[:3])
        summary = f"List of {count} items. First 3: {first_items}... and {count - 3} more."
    
    # Truncate if needed
    if len(summary) > max_length:
        summary = summary[:max_length-3] + "..."
    
    return {
        "text": summary,
        "key_points": [f"{count} total items", f"Types: {', '.join(item_types.keys())}"],
        "stats": {
            "count": count,
            "types": item_types,
            "sample": items[:3] if count > 3 else items
        }
    }


def summarize_data(data: dict, max_length: int) -> Dict[str, Any]:
    """Summarize structured data."""
    if not data:
        return {"text": "Empty data object", "key_points": [], "stats": {"keys": 0}}
    
    keys = list(data.keys())
    key_count = len(keys)
    
    # Analyze structure
    structure = {}
    for key, value in data.items():
        structure[key] = type(value).__name__
    
    # Create summary
    if key_count <= 5:
        key_list = ', '.join(keys)
        summary = f"Data object with {key_count} keys: {key_list}"
    else:
        key_list = ', '.join(keys[:3])
        summary = f"Data object with {key_count} keys. Main keys: {key_list}... and {key_count - 3} more."
    
    # Add value info
    nested_count = sum(1 for v in data.values() if isinstance(v, (dict, list)))
    if nested_count:
        summary += f" Contains {nested_count} nested structure(s)."
    
    # Truncate if needed
    if len(summary) > max_length:
        summary = summary[:max_length-3] + "..."
    
    return {
        "text": summary,
        "key_points": keys[:5],
        "stats": {
            "keys": key_count,
            "structure": structure,
            "nested_count": nested_count
        }
    }


if __name__ == "__main__":
    # Test the agent
    test_cases = [
        {
            "type": "text",
            "content": "The quick brown fox jumps over the lazy dog. This is a simple test sentence. Machine learning models are becoming more powerful. Natural language processing enables computers to understand human language. Artificial intelligence is transforming industries worldwide.",
            "max_length": 150
        },
        {
            "type": "list",
            "content": ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape"]
        },
        {
            "type": "data",
            "content": {"name": "John", "age": 30, "city": "NYC", "skills": ["python", "js"], "active": True}
        }
    ]
    
    for test in test_cases:
        print(f"\n{'='*50}")
        print(f"Input type: {test['type']}")
        result = handle(test, None)
        print(f"Summary: {result['output']['summary']}")
        print(f"Key points: {result['output']['key_points']}")
