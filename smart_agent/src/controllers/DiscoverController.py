"""
Discover Controller for the Old Fashioned Agent.

Returns the agent.json configuration for A2A protocol self-documentation.
"""

import json
import os
from typing import Dict, Any

from smart_agent.src.agent.agent_config import fetch_agent_config
from smart_agent.src.config.logger import Logger

logger = Logger()


def discover() -> Dict[str, Any]:
    """
    Return agent configuration for discovery endpoint.

    Returns:
        Agent configuration dictionary from agent.json
    """
    try:
        config = fetch_agent_config()
        logger.info("Discover endpoint called successfully")
        return config

    except Exception as e:
        logger.error(f"Error in discover: {str(e)}")
        return {
            "error": f"Failed to load agent configuration: {str(e)}",
            "code": 500
        }
