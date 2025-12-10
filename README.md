# Agreus Family Office Benchmark Agent

An OldFashioned-pattern Spritz agent that provides expert knowledge from the 2025 Agreus/KPMG Global Family Office Compensation Benchmark Report. Built with the Anthropic API and deployed on AWS Lambda.

## Features

- **Multi-turn conversations** with thread continuity
- **Knowledge base (Skills)** loaded from markdown files
- **HTML output** converted from LLM markdown responses
- **Webhook callbacks** for real-time status updates

## Architecture

```
agent-of-agreus/
├── lambda_handler.py          # AWS Lambda entry point with SSM config loading
├── Prompt/
│   └── AgentPrompt.yaml       # System and user prompt templates
├── Skill/
│   ├── SKILL.md               # Main knowledge base index
│   └── references/            # Regional and thematic data files
│       ├── regional-uk.md
│       ├── regional-europe.md
│       ├── regional-usa.md
│       └── ...
└── smart_agent/
    ├── main.py                # FastAPI application
    ├── requirements.txt       # Python dependencies
    └── src/
        ├── agent/
        │   ├── base_agent.py  # Core agent logic
        │   └── prompt_extract.py
        ├── config/
        │   └── agent.json     # A2A protocol schema
        ├── controllers/       # API endpoint handlers
        ├── routes/            # FastAPI routes
        └── utils/             # Helpers (webhook, temp_db)
```

## Threading Implementation (Anthropic API)

Unlike OpenAI's native `previous_response_id`, Anthropic doesn't have built-in thread management. This agent implements threading via UUID-based conversation storage:

### How It Works

1. **First message**: No `threadId` provided
   - Agent generates a new UUID (e.g., `dcb917d2-5160-4d83-b22e-ab0084a82da3`)
   - Conversation history stored in memory keyed by UUID
   - UUID returned to client as `threadId`

2. **Follow-up messages**: Client passes `threadId`
   - Agent retrieves conversation history from storage
   - Previous messages included in Anthropic API call
   - Same UUID returned (history updated)

### Code Overview

```python
# In-memory storage (Lambda instance scope)
_thread_storage: Dict[str, List[Dict[str, str]]] = {}

def get_thread_history(thread_id: Optional[str]) -> List[Dict[str, str]]:
    """Retrieve conversation history by UUID."""
    if not thread_id:
        return []
    return _thread_storage.get(thread_id, [])

def save_thread_history(thread_id: str, messages: List[Dict[str, str]]) -> str:
    """Save conversation history, return UUID."""
    if not thread_id:
        thread_id = str(uuid.uuid4())
    _thread_storage[thread_id] = messages
    return thread_id
```

### Limitations

- **In-memory storage**: Threads persist only while Lambda instance is warm
- **No cross-instance sharing**: Different Lambda instances have separate storage
- **For production**: Replace with DynamoDB for persistent, shared thread storage

## Skills System (Knowledge Base)

Skills provide domain knowledge that's injected into the system prompt. All files in the `Skill/` directory are loaded and appended to the prompt.

### Structure

```
Skill/
├── SKILL.md                   # Index with quick reference data
└── references/
    ├── regional-uk.md         # UK compensation data
    ├── regional-europe.md     # Europe compensation data
    ├── regional-usa.md        # USA compensation data
    ├── regional-asia.md       # Asia compensation data
    ├── regional-australia.md  # Australia compensation data
    ├── regional-middleeast.md # Middle East compensation data
    ├── investments.md         # Investment strategies
    ├── recruitment.md         # Hiring trends
    └── governance.md          # Governance practices
```

### How Skills Are Loaded

```python
def get_skill_dir() -> str:
    """Find skill directory (handles Lambda paths)."""
    paths = ['Skill', '/var/task/Skill', '/tmp/Skill']
    for path in paths:
        if os.path.exists(path):
            return path
    return 'Skill'

# In llm() function:
skill_dir = get_skill_dir()
if os.path.exists(skill_dir):
    skill_content = load_skill_content(skill_dir)
    if skill_content:
        system_prompt = f"{system_prompt}\n\n## Detailed Reference Data\n\n{skill_content}"
```

### Adding New Skills

1. Create markdown files in `Skill/` or `Skill/references/`
2. Files are automatically loaded at runtime
3. Content appended to system prompt as reference data

## HTML Output

The agent converts LLM markdown responses to HTML for better rendering in Spritz:

```python
import markdown

def markdown_to_html(text: str) -> str:
    """Convert markdown to HTML."""
    if not text:
        return ""
    return markdown.markdown(text)
```

**Note**: Conversation history is stored in markdown format (for LLM context continuity), but output is converted to HTML before returning to the client.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/discover` | GET | Returns agent.json schema |
| `/execute` | POST | Process a query |
| `/status` | GET | Check job status |
| `/abort` | POST | Cancel a running job |

### Execute Request

```json
{
  "inputs": [
    {"name": "payload", "data": "What is the average CEO salary in the UK?"},
    {"name": "threadId", "data": "optional-uuid-for-continuation"}
  ],
  "webhookUrl": "https://callback.url/for/status/updates"
}
```

### Execute Response

```json
{
  "id": "job-uuid",
  "status": "completed",
  "result": {
    "name": "output",
    "type": "longText",
    "data": "<p>Based on the 2025 benchmark...</p>"
  },
  "explanation": "Response derived from compensation data...",
  "threadId": "dcb917d2-5160-4d83-b22e-ab0084a82da3"
}
```

## Deployment

### Prerequisites

- AWS CLI configured
- Docker (for building Lambda-compatible packages)
- S3 bucket for deployment artifacts
- SSM parameters for secrets

### Build & Deploy

```bash
# Build deployment package
rm -rf package deployment.zip
mkdir -p package

docker run --rm --platform linux/amd64 \
  -v "$PWD":/var/task -w /var/task \
  public.ecr.aws/lambda/python:3.11 \
  pip install -r smart_agent/requirements.txt -t package/ --quiet

cp -r smart_agent package/
cp lambda_handler.py package/
cp -r Prompt package/
cp -r Skill package/

cd package && zip -r ../deployment.zip . -x "*.pyc" -x "__pycache__/*"

# Upload and deploy
aws s3 cp deployment.zip s3://your-bucket/agent-of-agreus/deployment.zip --region eu-west-2

aws lambda update-function-code \
  --function-name agent-of-agreus-dev \
  --s3-bucket your-bucket \
  --s3-key agent-of-agreus/deployment.zip \
  --region eu-west-2
```

### SSM Parameters

Create these in the deployment region:

```bash
aws ssm put-parameter --name "/app/agent-of-agreus/dev/ANTHROPIC_API_KEY" \
  --value "your-api-key" --type "SecureString" --region eu-west-2
```

## Testing

```bash
# Test discover
curl https://your-function-url.lambda-url.eu-west-2.on.aws/discover

# Test execute (new conversation)
curl -X POST "https://your-function-url.lambda-url.eu-west-2.on.aws/execute" \
  -H "Content-Type: application/json" \
  -d '{"inputs": [{"name": "payload", "data": "What is the average CEO salary in the UK?"}]}'

# Test thread continuity
curl -X POST "https://your-function-url.lambda-url.eu-west-2.on.aws/execute" \
  -H "Content-Type: application/json" \
  -d '{"inputs": [{"name": "payload", "data": "And what about bonuses?"}, {"name": "threadId", "data": "uuid-from-previous-response"}]}'
```

## Data Source

Based on the 2025 Agreus/KPMG Global Family Office Compensation Benchmark Report:
- 585 survey responses
- 20 qualitative interviews
- Coverage: UK, Europe, USA, Asia, Australia, Middle East
