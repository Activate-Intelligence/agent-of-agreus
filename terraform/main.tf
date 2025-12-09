# Terraform configuration for Agreus Family Office Benchmark Agent
# Old Fashioned Agent using Anthropic API

terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "your-terraform-state-bucket"
    region = "us-east-1"
    # key is set via -backend-config
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "agent-of-agreus"
}

variable "deployment_type" {
  description = "Deployment type: lambda, lambda_ecr, or ecs"
  type        = string
  default     = "lambda"
}

variable "s3_bucket" {
  description = "S3 bucket containing the deployment package"
  type        = string
}

variable "s3_key" {
  description = "S3 key for the deployment package"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 512
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 900
}

# Data sources
data "aws_caller_identity" "current" {}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.function_name}-${var.environment}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.function_name}-${var.environment}-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/app/${var.function_name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.jobs_table.arn
      }
    ]
  })
}

# Lambda Function
resource "aws_lambda_function" "agent" {
  function_name = "${var.function_name}-${var.environment}"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = var.timeout
  memory_size   = var.memory_size

  s3_bucket = var.s3_bucket
  s3_key    = var.s3_key

  environment {
    variables = {
      AGENT_NAME       = var.function_name
      ENVIRONMENT      = var.environment
      SSM_PREFIX       = "/app/${var.function_name}/${var.environment}"
      DYNAMODB_TABLE   = aws_dynamodb_table.jobs_table.name
      ENVIRONMENT_MODE = "prod"
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_policy
  ]
}

# Lambda Function URL (alternative to API Gateway)
resource "aws_lambda_function_url" "agent_url" {
  function_name      = aws_lambda_function.agent.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST", "OPTIONS"]
    allow_headers     = ["*"]
    max_age           = 86400
  }
}

# API Gateway
resource "aws_apigatewayv2_api" "agent_api" {
  name          = "${var.function_name}-${var.environment}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["*"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.agent_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id             = aws_apigatewayv2_api.agent_api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.agent.invoke_arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.agent_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.agent.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.agent_api.execution_arn}/*/*"
}

# DynamoDB Table for job state
resource "aws_dynamodb_table" "jobs_table" {
  name         = "${var.function_name}-${var.environment}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Environment = var.environment
    Agent       = var.function_name
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "agent_logs" {
  name              = "/aws/lambda/${var.function_name}-${var.environment}"
  retention_in_days = 14
}

# Outputs
output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.agent_api.api_endpoint
}

output "lambda_function_url" {
  description = "Lambda Function URL"
  value       = aws_lambda_function_url.agent_url.function_url
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.agent.function_name
}

output "dynamodb_table" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.jobs_table.name
}
