"""
Smart skill loading with query-based file selection.

Implements a two-tier approach inspired by Anthropic's Agent Skills pattern:
1. Level 1: Skill metadata (from SKILL.md frontmatter) always loaded
2. Level 2: Relevant reference files loaded based on query classification

Since this is a single-turn API agent (not agentic with tool use), we use
keyword matching to determine which skill files are relevant to the query.
"""

import os
import re
import yaml
from typing import Dict, List, Optional, Tuple
from smart_agent.src.config.logger import Logger

logger = Logger()

# Skill file metadata with keywords for matching
SKILL_FILES = {
    "regional-uk.md": {
        "keywords": ["uk", "united kingdom", "britain", "british", "london", "gbp", "£"],
        "description": "UK family office compensation data"
    },
    "regional-europe.md": {
        "keywords": ["europe", "european", "eu", "germany", "france", "switzerland", "eur", "€"],
        "description": "Continental Europe compensation data"
    },
    "regional-usa.md": {
        "keywords": ["usa", "us", "united states", "america", "american", "usd", "$", "new york", "california"],
        "description": "USA family office compensation data"
    },
    "regional-asia.md": {
        "keywords": ["asia", "asian", "singapore", "hong kong", "china", "japan", "india"],
        "description": "Asia family office compensation data"
    },
    "regional-australia.md": {
        "keywords": ["australia", "australian", "sydney", "melbourne", "aud"],
        "description": "Australia family office compensation data"
    },
    "regional-middleeast.md": {
        "keywords": ["middle east", "uae", "dubai", "saudi", "arabia", "qatar", "gulf"],
        "description": "Middle East family office compensation data"
    },
    "governance.md": {
        "keywords": ["governance", "succession", "structure", "board", "family council", "next gen", "professionalisation"],
        "description": "Family office governance and succession planning"
    },
    "investments.md": {
        "keywords": ["investment", "invest", "portfolio", "allocation", "asset", "roi", "return", "equity", "real estate", "private"],
        "description": "Investment strategies and asset allocation"
    },
    "recruitment.md": {
        "keywords": ["recruit", "hiring", "hire", "talent", "team", "staff", "employee", "headcount", "remote", "turnover"],
        "description": "Recruitment trends and talent management"
    }
}

# Keywords that indicate compensation-related queries (load all regional files)
COMPENSATION_KEYWORDS = ["salary", "salaries", "compensation", "pay", "bonus", "ltip", "incentive", "benefits", "package"]

# Role keywords (may need multiple regional files for comparison)
ROLE_KEYWORDS = ["ceo", "cfo", "cio", "chief", "director", "manager", "analyst", "head of"]


def get_skill_dir() -> str:
    """Get the skill directory path."""
    paths = ['Skill', '/var/task/Skill', '/tmp/Skill']
    for path in paths:
        if os.path.exists(path):
            return path
    return 'Skill'


def parse_skill_metadata(skill_dir: str) -> Dict[str, str]:
    """
    Parse SKILL.md frontmatter for metadata.

    Returns:
        Dictionary with 'name' and 'description' from YAML frontmatter
    """
    skill_md_path = os.path.join(skill_dir, 'SKILL.md')

    if not os.path.exists(skill_md_path):
        return {"name": "Unknown Skill", "description": ""}

    with open(skill_md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract YAML frontmatter between --- markers
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if frontmatter_match:
        try:
            metadata = yaml.safe_load(frontmatter_match.group(1))
            return {
                "name": metadata.get("name", "Unknown Skill"),
                "description": metadata.get("description", "")
            }
        except yaml.YAMLError:
            pass

    return {"name": "Unknown Skill", "description": ""}


def classify_query(query: str) -> List[str]:
    """
    Classify a query to determine which skill files are relevant.

    Args:
        query: The user's question/request

    Returns:
        List of relevant skill file names
    """
    query_lower = query.lower()
    relevant_files = set()

    # Check for compensation keywords - these often need regional context
    has_compensation_query = any(kw in query_lower for kw in COMPENSATION_KEYWORDS)
    has_role_query = any(kw in query_lower for kw in ROLE_KEYWORDS)

    # Check each skill file's keywords
    for filename, config in SKILL_FILES.items():
        for keyword in config["keywords"]:
            if keyword in query_lower:
                relevant_files.add(filename)
                break

    # If asking about compensation/roles but no specific region, might be general query
    # In this case, we could load the main SKILL.md which has overview data

    # If asking about comparison between regions, load multiple
    comparison_words = ["compare", "comparison", "vs", "versus", "difference", "between"]
    if any(word in query_lower for word in comparison_words):
        # Load all mentioned regional files
        pass  # Already handled by keyword matching

    logger.info(f"Query classification: {len(relevant_files)} relevant files for query: {query[:50]}...")
    logger.info(f"Relevant files: {list(relevant_files)}")

    return list(relevant_files)


def load_skill_metadata(skill_dir: str) -> str:
    """
    Load Level 1 content: skill metadata and quick reference.
    This is always included in the prompt.

    Args:
        skill_dir: Path to the Skill directory

    Returns:
        Skill metadata and quick reference section
    """
    skill_md_path = os.path.join(skill_dir, 'SKILL.md')

    if not os.path.exists(skill_md_path):
        return ""

    with open(skill_md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return content


def load_relevant_skills(skill_dir: str, query: str) -> Tuple[str, List[str]]:
    """
    Load skill content relevant to the query using two-tier approach.

    Level 1: Always load SKILL.md (metadata + quick reference)
    Level 2: Load specific reference files based on query classification

    Args:
        skill_dir: Path to the Skill directory
        query: The user's question/request

    Returns:
        Tuple of (combined skill content, list of loaded files)
    """
    loaded_files = []
    content_parts = []

    # Level 1: Always load main SKILL.md
    skill_md_path = os.path.join(skill_dir, 'SKILL.md')
    if os.path.exists(skill_md_path):
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content_parts.append(f"# Skill Overview\n{f.read()}")
            loaded_files.append("SKILL.md")

    # Level 2: Load relevant reference files based on query
    relevant_files = classify_query(query)
    references_dir = os.path.join(skill_dir, 'references')

    if os.path.exists(references_dir) and relevant_files:
        for filename in relevant_files:
            filepath = os.path.join(references_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    content_parts.append(f.read())
                    loaded_files.append(f"references/{filename}")

    # If no specific files matched but it's a compensation query, load all regional files
    if not relevant_files:
        query_lower = query.lower()
        if any(kw in query_lower for kw in COMPENSATION_KEYWORDS + ROLE_KEYWORDS):
            logger.info("No specific region detected, loading all reference files for comprehensive response")
            if os.path.exists(references_dir):
                for filename in sorted(os.listdir(references_dir)):
                    if filename.endswith('.md'):
                        filepath = os.path.join(references_dir, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content_parts.append(f.read())
                            loaded_files.append(f"references/{filename}")

    combined_content = '\n\n---\n\n'.join(content_parts)

    logger.info(f"Loaded {len(loaded_files)} skill files: {loaded_files}")

    return combined_content, loaded_files


def get_available_skills_summary(skill_dir: str) -> str:
    """
    Generate a summary of available skill files for the system prompt.
    This helps the LLM understand what data is available.

    Args:
        skill_dir: Path to the Skill directory

    Returns:
        Formatted summary of available skills
    """
    lines = ["## Available Reference Data"]

    for filename, config in SKILL_FILES.items():
        lines.append(f"- **{filename}**: {config['description']}")

    return "\n".join(lines)
