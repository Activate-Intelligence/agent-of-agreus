import yaml
import re
from typing import Tuple, Dict, Any, Optional


def extract_prompts(
    yaml_file_path: str,
    **variables
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Extract system prompt, user prompt, and model parameters from a YAML file.

    Args:
        yaml_file_path: Path to the YAML prompt file
        **variables: Variables to substitute in the prompts (e.g., instructions="...", payload="...")

    Returns:
        Tuple of (system_prompt, user_prompt, model_params)
    """
    with open(yaml_file_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    model_params = data.get('model', {
        'name': 'claude-sonnet-4-20250514',
        'temperature': 0.7,
        'max_tokens': 4096
    })

    prompt_content = data.get('prompt', '')

    # Substitute variables using {{variable}} syntax
    for key, value in variables.items():
        placeholder = f'{{{{{key}}}}}'
        if value is not None:
            prompt_content = prompt_content.replace(placeholder, str(value))
        else:
            prompt_content = prompt_content.replace(placeholder, '')

    # Extract system and user messages using XML-style tags
    system_prompt = extract_message(prompt_content, 'system')
    user_prompt = extract_message(prompt_content, 'user')

    return system_prompt, user_prompt, model_params


def extract_message(content: str, role: str) -> str:
    """
    Extract message content for a specific role from XML-style tags.

    Args:
        content: The full prompt content
        role: The role to extract ('system' or 'user')

    Returns:
        The extracted message content, stripped of whitespace
    """
    pattern = rf'<message role="{role}">(.*?)</message>'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(1).strip()

    return ''


def load_skill_content(skill_dir: str) -> str:
    """
    Load and concatenate skill reference files for inclusion in the system prompt.

    Args:
        skill_dir: Path to the Skill directory

    Returns:
        Concatenated content from all reference files
    """
    import os

    content_parts = []

    # Load main SKILL.md
    skill_md_path = os.path.join(skill_dir, 'SKILL.md')
    if os.path.exists(skill_md_path):
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content_parts.append(f"# Skill Overview\n{f.read()}")

    # Load reference files
    references_dir = os.path.join(skill_dir, 'references')
    if os.path.exists(references_dir):
        for filename in sorted(os.listdir(references_dir)):
            if filename.endswith('.md'):
                filepath = os.path.join(references_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content_parts.append(f.read())

    return '\n\n---\n\n'.join(content_parts)
