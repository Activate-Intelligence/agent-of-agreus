"""
Old Fashioned Agent using Anthropic API with threading support.

This agent provides expert knowledge about the 2025 Agreus/KPMG Global Family Office
Compensation Benchmark Report. It supports multi-turn conversations by maintaining
conversation history through a thread ID stored in DynamoDB.

Features:
- Persistent thread storage via DynamoDB
- Smart skill loading based on query classification
- HTML output conversion from markdown
"""

import os
from typing import Tuple, Optional, Dict, Any, List

import anthropic
import markdown

from smart_agent.src.config.logger import Logger
from smart_agent.src.utils.webhook import call_webhook_with_error, call_webhook_with_success
from smart_agent.src.utils.thread_storage import get_thread, save_thread
from smart_agent.src.agent.prompt_extract import extract_prompts
from smart_agent.src.agent.skill_loader import load_relevant_skills, get_skill_dir
from smart_agent.src.agent.agent_config import fetch_agent_config

# Environment mode: "dev" or "prod"
ENVIRONMENT_MODE = os.environ.get("ENVIRONMENT_MODE", "dev")

logger = Logger()

# Lazy-loaded Anthropic client
_client = None


def get_anthropic_client():
    """
    Get or create the Anthropic client (lazy initialization).
    This ensures the client is created after SSM parameters are loaded.
    """
    global _client
    if _client is None:
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        _client = anthropic.Anthropic(api_key=anthropic_api_key)
    return _client


def get_prompt_file_path(filename: str) -> str:
    """
    Get the appropriate path for prompt files based on environment mode.

    In dev mode, checks /tmp first (for hot-reloading from Git).
    In prod mode, uses bundled Prompt/ folder.
    """
    if ENVIRONMENT_MODE == "dev":
        tmp_path = f'/tmp/Prompt/{filename}'
        if os.path.exists(tmp_path):
            return tmp_path

    # Check multiple possible locations
    paths = [
        f'Prompt/{filename}',
        f'/var/task/Prompt/{filename}',
        f'smart_agent/../Prompt/{filename}',
    ]

    for path in paths:
        if os.path.exists(path):
            return path

    return f'Prompt/{filename}'


def markdown_to_html(text: str) -> str:
    """
    Convert markdown text to HTML.

    Args:
        text: Markdown formatted text

    Returns:
        HTML formatted text
    """
    if not text:
        return ""

    # Convert markdown to HTML
    html = markdown.markdown(text)

    return html


def extract_reasoning_summary(response_text: str, loaded_files: Optional[List[str]] = None) -> str:
    """
    Extract a reasoning summary from the response.

    For Old Fashioned agents, we provide an explanation of how the response
    was derived based on the benchmark data.

    Args:
        response_text: The LLM's response text
        loaded_files: List of skill files that were loaded for this query

    Returns:
        Explanation string describing data sources
    """
    if not response_text:
        return "No response generated."

    # Check for key topics in the response to create relevant explanation
    topics = []

    if any(term in response_text.lower() for term in ['salary', 'compensation', '£', '$', '€']):
        topics.append("compensation data")

    if any(term in response_text.lower() for term in ['bonus', 'ltip', 'incentive']):
        topics.append("bonus and incentive structures")

    if any(term in response_text.lower() for term in ['uk', 'usa', 'europe', 'asia', 'middle east', 'australia']):
        topics.append("regional market analysis")

    if any(term in response_text.lower() for term in ['governance', 'succession', 'structure']):
        topics.append("governance and organizational data")

    if any(term in response_text.lower() for term in ['invest', 'roi', 'allocation', 'portfolio']):
        topics.append("investment strategy insights")

    if any(term in response_text.lower() for term in ['hiring', 'recruitment', 'talent', 'team']):
        topics.append("recruitment and talent trends")

    # Build explanation
    base = "2025 Agreus/KPMG Global Family Office Compensation Benchmark Report (585 survey responses, 20 qualitative interviews)"

    if topics:
        explanation = f"Response derived from {', '.join(topics)} in the {base}."
    else:
        explanation = f"Response based on the {base}."

    # Add loaded files info
    if loaded_files and len(loaded_files) > 1:
        file_names = [f.replace('references/', '').replace('.md', '') for f in loaded_files if f != 'SKILL.md']
        if file_names:
            explanation += f" Sources: {', '.join(file_names)}."

    return explanation


def llm(
    payload: str,
    instructions: Optional[str] = None,
    thread_id: Optional[str] = None
) -> Tuple[str, str, str, List[str]]:
    """
    Call the Anthropic API with threading support and smart skill loading.

    Args:
        payload: The user's question or request
        instructions: Optional specific instructions for the query
        thread_id: UUID of the conversation thread for continuity

    Returns:
        Tuple of (response_html, explanation, new_thread_id, loaded_skill_files)
    """
    # Load prompt template
    prompt_file_path = get_prompt_file_path('AgentPrompt.yaml')
    system_prompt, user_prompt_template, model_params = extract_prompts(
        prompt_file_path,
        instructions=instructions or "Answer the user's question based on the benchmark data.",
        payload=payload
    )

    # Smart skill loading: only load relevant files based on query
    skill_dir = get_skill_dir()
    loaded_files = []
    if os.path.exists(skill_dir):
        skill_content, loaded_files = load_relevant_skills(skill_dir, payload)
        if skill_content:
            system_prompt = f"{system_prompt}\n\n## Reference Data\n\n{skill_content}"

    logger.info(f"Loaded {len(loaded_files)} skill files for query")

    # Retrieve existing conversation history from DynamoDB
    conversation_history = get_thread(thread_id)

    # Build messages for Anthropic API
    messages = []

    # Add conversation history if exists
    for msg in conversation_history:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    # Add current user message
    messages.append({
        "role": "user",
        "content": payload
    })

    logger.info(f"Calling Anthropic API with model: {model_params.get('name', 'claude-sonnet-4-20250514')}")
    logger.info(f"Conversation has {len(messages)} messages")

    # Get Anthropic client (lazy initialization)
    client = get_anthropic_client()

    # Call Anthropic API
    response = client.messages.create(
        model=model_params.get('name', 'claude-sonnet-4-20250514'),
        max_tokens=model_params.get('max_tokens', 4096),
        temperature=model_params.get('temperature', 0.7),
        system=system_prompt,
        messages=messages
    )

    # Extract response text (markdown format from LLM)
    response_markdown = ""
    for block in response.content:
        if block.type == "text":
            response_markdown += block.text

    response_markdown = response_markdown.strip()

    # Generate explanation with loaded files info
    explanation = extract_reasoning_summary(response_markdown, loaded_files)

    # Update conversation history with markdown (for context continuity)
    messages.append({
        "role": "assistant",
        "content": response_markdown
    })

    # Save updated history to DynamoDB and get thread UUID
    new_thread_id = save_thread(thread_id, messages)

    # Convert markdown to HTML for output
    response_html = markdown_to_html(response_markdown)

    logger.info(f"Response generated. Tokens used: {response.usage.input_tokens} in, {response.usage.output_tokens} out")

    return response_html, explanation, new_thread_id, loaded_files


def base_agent(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]:
    """
    Main agent entry point.

    Args:
        payload: Dictionary containing:
            - id: Job ID for webhook callbacks
            - payload: User's question/request
            - instructions: Optional specific instructions
            - threadId: Optional thread ID for conversation continuity

    Returns:
        Tuple of (response_dict, explanation, thread_id)
    """
    job_id = payload.get('id')
    user_payload = payload.get('payload', '')
    instructions = payload.get('instructions')
    thread_id = payload.get('threadId')

    try:
        # Send progress update
        call_webhook_with_success(job_id, {
            "status": "inprogress",
            "data": {
                "title": "Processing...",
                "info": "Analyzing family office benchmark data..."
            }
        })

        # Call LLM with threading support and smart skill loading
        response_text, explanation, new_thread_id, loaded_files = llm(
            payload=user_payload,
            instructions=instructions,
            thread_id=thread_id
        )

        logger.info(f"Skill files used: {loaded_files}")

        # Prepare response
        resp = {
            "name": "output",
            "type": "longText",
            "data": response_text
        }

        # Send explanation via webhook
        call_webhook_with_success(job_id, {
            "status": "inprogress",
            "data": {
                "output": {
                    "name": "explanation",
                    "type": "longText",
                    "data": explanation
                }
            }
        })

        # Send thread ID via webhook
        call_webhook_with_success(job_id, {
            "status": "inprogress",
            "data": {
                "output": {
                    "name": "threadId",
                    "type": "shortText",
                    "data": new_thread_id
                }
            }
        })

        logger.info(f"Agent completed successfully for job {job_id}")
        return resp, explanation, new_thread_id

    except anthropic.APIConnectionError as e:
        error_msg = f"Failed to connect to Anthropic API: {str(e)}"
        logger.error(error_msg)
        call_webhook_with_error(job_id, error_msg, 503)
        raise

    except anthropic.RateLimitError as e:
        error_msg = f"Anthropic API rate limit exceeded: {str(e)}"
        logger.error(error_msg)
        call_webhook_with_error(job_id, error_msg, 429)
        raise

    except anthropic.APIStatusError as e:
        error_msg = f"Anthropic API error: {str(e)}"
        logger.error(error_msg)
        call_webhook_with_error(job_id, error_msg, e.status_code)
        raise

    except Exception as e:
        error_msg = f"Error in base_agent: {str(e)}"
        logger.error(error_msg)
        call_webhook_with_error(job_id, error_msg, 500)
        raise
