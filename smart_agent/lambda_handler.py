"""
AWS Lambda handler with SSM configuration loading.

Loads configuration from AWS Systems Manager Parameter Store
and initializes the FastAPI application with Mangum for Lambda.
"""

import os
import json
import boto3
from botocore.exceptions import ClientError

# SSM Parameter aliases mapping
parameter_aliases = {
    'APP_PORT': ['app_port', 'port'],
    'APP_HOST': ['app_host', 'host'],
    'ALLOW_ORIGINS': ['allow_origins', 'cors_origins'],
    'ANTHROPIC_API_KEY': ['anthropic_api_key', 'anthropic_key'],
    'AGENT_EXECUTE_LIMIT': ['agent_execute_limit', 'execute_limit'],
    'AGENT_NAME': ['agent_name', 'name'],
    'AGENT_TYPE': ['agent_type', 'type'],
    'WEBHOOK_URL': ['webhook_url', 'callback_url'],
    'DYNAMODB_TABLE': ['dynamodb_table', 'jobs_table'],
    'ENVIRONMENT_MODE': ['environment_mode', 'env_mode'],
}


def get_ssm_parameters(prefix: str) -> dict:
    """
    Load parameters from AWS SSM Parameter Store.

    Args:
        prefix: SSM parameter path prefix (e.g., /app/agent-name/dev)

    Returns:
        Dictionary of parameter names to values
    """
    ssm = boto3.client('ssm')
    parameters = {}

    try:
        paginator = ssm.get_paginator('get_parameters_by_path')
        pages = paginator.paginate(
            Path=prefix,
            Recursive=True,
            WithDecryption=True
        )

        for page in pages:
            for param in page['Parameters']:
                # Extract parameter name from full path
                name = param['Name'].split('/')[-1].upper()
                parameters[name] = param['Value']

        return parameters

    except ClientError as e:
        print(f"Error loading SSM parameters: {e}")
        return {}


def resolve_parameter_name(name: str, parameters: dict) -> str:
    """
    Resolve a parameter name considering aliases.

    Args:
        name: The canonical parameter name
        parameters: Dictionary of loaded parameters

    Returns:
        The parameter value or empty string
    """
    # Check canonical name first
    if name in parameters:
        return parameters[name]

    # Check aliases
    aliases = parameter_aliases.get(name, [])
    for alias in aliases:
        upper_alias = alias.upper()
        if upper_alias in parameters:
            return parameters[upper_alias]

    return ""


def load_config():
    """
    Load configuration from SSM or environment variables.
    """
    # Determine SSM prefix from environment
    agent_name = os.environ.get('AGENT_NAME', 'agent-of-agreus')
    environment = os.environ.get('ENVIRONMENT', 'dev')
    ssm_prefix = os.environ.get('SSM_PREFIX', f'/app/{agent_name}/{environment}')

    # Try to load from SSM
    ssm_params = get_ssm_parameters(ssm_prefix)

    # Set environment variables from SSM parameters
    for param_name in parameter_aliases.keys():
        value = resolve_parameter_name(param_name, ssm_params)
        if value and param_name not in os.environ:
            os.environ[param_name] = value

    # Ensure critical env vars have defaults
    if 'ENVIRONMENT_MODE' not in os.environ:
        os.environ['ENVIRONMENT_MODE'] = 'prod'


# Load configuration on module import
load_config()

# Import FastAPI app after config is loaded
from mangum import Mangum
from smart_agent.main import app

# Create Lambda handler
handler = Mangum(app, lifespan="off")


def lambda_handler(event, context):
    """
    AWS Lambda entry point.

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        API Gateway response
    """
    return handler(event, context)
