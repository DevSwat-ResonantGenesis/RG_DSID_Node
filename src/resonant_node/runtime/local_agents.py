"""
Local Agent Registry
====================
Maps manifest hashes to local agent files for development/testing.
"""

from pathlib import Path
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)

# Map manifest hash -> local agent directory
LOCAL_AGENTS = {
    # Hello World Agent
    "0x6bf8e4988147478a64f0a72eb2b411df6b3256167c2347c72cefcd4d444ea7f1": {
        "name": "Hello World Agent",
        "path": "agents/hello-world",
        "manifest": "manifest.json",
        "entrypoint": "main.py",
    },
    # Code Analyzer Agent
    "0xfc6a5c495a6986f2ca339e86af0a9a527b58cfa99d94518539c22a524714856f": {
        "name": "Code Analyzer Agent",
        "path": "agents/code-analyzer",
        "manifest": "manifest.json",
        "entrypoint": "main.py",
    },
    # Data Summarizer Agent
    "0x97a2c7910d3dac4b47011d91bbb6dc01089811f99d264d9fe8105cbca2188144": {
        "name": "Data Summarizer Agent",
        "path": "agents/data-summarizer",
        "manifest": "manifest.json",
        "entrypoint": "main.py",
    },
    # Task Planner Agent
    "0x8979fb0e028cb36e3925943b9b9f9fb3ad183c707924952610f47ad96e3dd04d": {
        "name": "Task Planner Agent",
        "path": "agents/task-planner",
        "manifest": "manifest.json",
        "entrypoint": "main.py",
    },
    # JSON Validator Agent
    "0x05634dfafb6990c1e6760bbb90f640912e3b1ef7c0f68aa1c5f456e6265256fe": {
        "name": "JSON Validator Agent",
        "path": "agents/json-validator",
        "manifest": "manifest.json",
        "entrypoint": "main.py",
    },
}


def get_project_root() -> Path:
    """Get the project root directory."""
    # Navigate from node/src/resonant_node/runtime to project root
    current = Path(__file__).resolve()
    # Go up: runtime -> resonant_node -> src -> node -> project_root
    return current.parent.parent.parent.parent.parent


def get_local_agent(manifest_hash: str) -> Optional[dict]:
    """
    Get local agent info by manifest hash.
    
    Returns dict with:
        - name: Agent name
        - path: Full path to agent directory
        - manifest_path: Full path to manifest.json
        - code_path: Full path to main code file
        - manifest: Parsed manifest dict
    """
    if manifest_hash not in LOCAL_AGENTS:
        return None
    
    agent_info = LOCAL_AGENTS[manifest_hash]
    project_root = get_project_root()
    agent_dir = project_root / agent_info["path"]
    
    if not agent_dir.exists():
        logger.warning(f"Agent directory not found: {agent_dir}")
        return None
    
    manifest_path = agent_dir / agent_info["manifest"]
    code_path = agent_dir / agent_info["entrypoint"]
    
    if not manifest_path.exists():
        logger.warning(f"Manifest not found: {manifest_path}")
        return None
    
    if not code_path.exists():
        logger.warning(f"Code not found: {code_path}")
        return None
    
    # Load manifest
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load manifest: {e}")
        return None
    
    return {
        "name": agent_info["name"],
        "path": str(agent_dir),
        "manifest_path": str(manifest_path),
        "code_path": str(code_path),
        "manifest": manifest,
    }


def get_local_agent_code(manifest_hash: str) -> Optional[str]:
    """Get the code content for a local agent."""
    agent = get_local_agent(manifest_hash)
    if not agent:
        return None
    
    try:
        with open(agent["code_path"]) as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read agent code: {e}")
        return None


def get_local_manifest(manifest_hash: str) -> Optional[dict]:
    """Get the manifest for a local agent."""
    agent = get_local_agent(manifest_hash)
    if not agent:
        return None
    return agent["manifest"]


def list_local_agents() -> list[dict]:
    """List all registered local agents."""
    agents = []
    for hash_id, info in LOCAL_AGENTS.items():
        agent = get_local_agent(hash_id)
        if agent:
            agents.append({
                "manifest_hash": hash_id,
                "name": info["name"],
                "path": agent["path"],
            })
    return agents
