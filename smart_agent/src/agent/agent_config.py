import json
import os
from typing import Dict, Any


def fetch_agent_config() -> Dict[str, Any]:
    """
    Load agent configuration from agent.json file.

    Returns:
        Dictionary containing agent configuration
    """
    config_paths = [
        'smart_agent/src/config/agent.json',
        'src/config/agent.json',
        '/var/task/smart_agent/src/config/agent.json',
    ]

    for path in config_paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)

    # Return default config if file not found
    return {
        "name": "Agreus Family Office Benchmark Agent",
        "description": "Expert agent for family office compensation benchmarks",
        "maxThreads": 1
    }


def get_input_schema() -> list:
    """Get the input schema from agent configuration."""
    config = fetch_agent_config()
    return config.get('inputs', [])


def get_output_schema() -> list:
    """Get the output schema from agent configuration."""
    config = fetch_agent_config()
    return config.get('outputs', [])
