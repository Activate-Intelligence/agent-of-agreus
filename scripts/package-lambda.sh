#!/bin/bash
# Lambda packaging script for Agreus Family Office Benchmark Agent
# Uses Docker to build for Linux x86_64 architecture

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building Lambda deployment package..."
echo "Project directory: $PROJECT_DIR"

# Clean up previous builds
rm -rf "$PROJECT_DIR/package"
rm -f "$PROJECT_DIR/deployment.zip"

# Create package directory
mkdir -p "$PROJECT_DIR/package"

# Install dependencies using Docker with x86_64 platform
echo "Installing dependencies with Docker..."
docker run --rm \
  --platform linux/amd64 \
  --entrypoint /bin/bash \
  -v "$PROJECT_DIR":/var/task \
  -w /var/task \
  public.ecr.aws/lambda/python:3.11 \
  -c "pip install -r smart_agent/requirements.txt -t package/"

# Copy source code
echo "Copying source files..."
cp -r "$PROJECT_DIR/smart_agent" "$PROJECT_DIR/package/"
cp "$PROJECT_DIR/lambda_handler.py" "$PROJECT_DIR/package/"
cp -r "$PROJECT_DIR/Prompt" "$PROJECT_DIR/package/"
cp -r "$PROJECT_DIR/Skill" "$PROJECT_DIR/package/"

# Create deployment zip
echo "Creating deployment.zip..."
cd "$PROJECT_DIR/package" && zip -r ../deployment.zip . -x "*.pyc" -x "__pycache__/*" -x "*.dist-info/*" && cd ..

# Clean up
rm -rf "$PROJECT_DIR/package"

echo "Done! Deployment package created: $PROJECT_DIR/deployment.zip"
echo ""
echo "To upload to S3:"
echo "  aws s3 cp deployment.zip s3://YOUR_BUCKET/agent-of-agreus/deployment.zip"
echo ""
echo "To update Lambda:"
echo "  aws lambda update-function-code --function-name agent-of-agreus-dev --s3-bucket YOUR_BUCKET --s3-key agent-of-agreus/deployment.zip"
