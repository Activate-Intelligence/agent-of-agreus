"""
Root Lambda handler entry point.

This file imports and re-exports the handler from the smart_agent package.
"""

from smart_agent.lambda_handler import lambda_handler as handler


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
