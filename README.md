# Agreus Family Office Benchmark Agent

An OldFashioned-pattern Spritz agent that provides expert knowledge from the 2025 Agreus/KPMG Global Family Office Compensation Benchmark Report. Built with the Anthropic API and deployed on AWS Lambda.

## Features

- **Multi-turn conversations** with persistent thread storage (DynamoDB)
- **Smart skill loading** - only loads relevant knowledge files based on query
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
        │   ├── skill_loader.py # Smart skill loading
        │   └── prompt_extract.py
        ├── config/
        │   └── agent.json     # A2A protocol schema
        ├── controllers/       # API endpoint handlers
        ├── routes/            # FastAPI routes
        └── utils/
            ├── thread_storage.py # DynamoDB thread persistence
            ├── webhook.py
            └── temp_db.py
```

## Threading Implementation (Anthropic API)

Unlike OpenAI's native `previous_response_id`, Anthropic doesn't have built-in thread management. This agent implements threading via UUID-based conversation storage in DynamoDB.

### How It Works

1. **First message**: No `threadId` provided
   - Agent generates a new UUID (e.g., `059308c6-ea59-44bf-9524-b90bec4c363e`)
   - Conversation history stored in DynamoDB
   - UUID returned to client as `threadId`

2. **Follow-up messages**: Client passes `threadId`
   - Agent retrieves conversation history from DynamoDB
   - Previous messages included in Anthropic API call
   - Same UUID returned (history updated)

### DynamoDB Schema

```
Table: agent-threads
Primary Key: thread_id (String)

Item Structure:
{
  "thread_id": "uuid-string",
  "messages": "[{\"role\": \"user\", \"content\": \"...\"}, ...]",
  "message_count": 4,
  "updated_at": "2025-12-10T13:38:19.255103",
  "ttl": 1736517499  // 30-day expiration
}
```

### Code Overview

```python
# smart_agent/src/utils/thread_storage.py

def get_thread(thread_id: str) -> List[Dict[str, str]]:
    """Retrieve conversation history from DynamoDB by UUID."""
    table = get_threads_table()
    response = table.get_item(Key={"thread_id": thread_id})
    if "Item" in response:
        return json.loads(response["Item"].get("messages", "[]"))
    return []

def save_thread(thread_id: Optional[str], messages: List[Dict[str, str]]) -> str:
    """Save conversation history to DynamoDB, return UUID."""
    if not thread_id:
        thread_id = str(uuid.uuid4())

    table.put_item(Item={
        "thread_id": thread_id,
        "messages": json.dumps(messages),
        "message_count": len(messages),
        "updated_at": datetime.utcnow().isoformat(),
        "ttl": int((datetime.utcnow() + timedelta(days=30)).timestamp())
    })
    return thread_id
```

### Benefits

- **Persistent**: Threads survive Lambda cold starts and scale across instances
- **Automatic cleanup**: TTL removes old threads after 30 days
- **Fallback**: In-memory storage if DynamoDB unavailable

## Smart Skill Loading

Inspired by [Anthropic's Agent Skills pattern](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills), this agent implements query-based skill selection to reduce token usage.

### Two-Tier Approach

Instead of loading all ~40KB of skill content into every prompt:

**Level 1**: Always load `SKILL.md` (metadata + quick reference)
**Level 2**: Load specific reference files based on query classification

### How It Works

```python
# smart_agent/src/agent/skill_loader.py

SKILL_FILES = {
    "regional-uk.md": {
        "keywords": ["uk", "united kingdom", "britain", "london", "gbp", "£"],
        "description": "UK family office compensation data"
    },
    "regional-usa.md": {
        "keywords": ["usa", "us", "united states", "america", "usd", "$"],
        "description": "USA family office compensation data"
    },
    # ... more files
}

def classify_query(query: str) -> List[str]:
    """Determine which skill files are relevant to the query."""
    query_lower = query.lower()
    relevant_files = set()

    for filename, config in SKILL_FILES.items():
        for keyword in config["keywords"]:
            if keyword in query_lower:
                relevant_files.add(filename)
                break

    return list(relevant_files)

def load_relevant_skills(skill_dir: str, query: str) -> Tuple[str, List[str]]:
    """Load only relevant skill files based on query."""
    # Level 1: Always load SKILL.md
    content_parts = [load_file("SKILL.md")]

    # Level 2: Load relevant reference files
    relevant_files = classify_query(query)
    for filename in relevant_files:
        content_parts.append(load_file(f"references/{filename}"))

    return combined_content, loaded_files
```

### Example

Query: "What is the average CEO salary in the UK?"
- Loads: `SKILL.md` + `regional-uk.md` (~6KB instead of ~40KB)

Query: "How does UK compare to USA?"
- Loads: `SKILL.md` + `regional-uk.md` + `regional-usa.md`

### Skill Files

| File | Keywords | Description |
|------|----------|-------------|
| `regional-uk.md` | uk, britain, london, £ | UK compensation data |
| `regional-usa.md` | usa, america, $, new york | USA compensation data |
| `regional-europe.md` | europe, germany, france, € | Europe compensation data |
| `regional-asia.md` | asia, singapore, hong kong | Asia compensation data |
| `regional-australia.md` | australia, sydney, aud | Australia compensation data |
| `regional-middleeast.md` | middle east, uae, dubai | Middle East compensation data |
| `governance.md` | governance, succession, board | Governance practices |
| `investments.md` | investment, portfolio, roi | Investment strategies |
| `recruitment.md` | recruit, hiring, talent | Hiring trends |

## HTML Output

The agent converts LLM markdown responses to HTML for better rendering in Spritz:

```python
import markdown

def markdown_to_html(text: str) -> str:
    """Convert markdown to HTML."""
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
  "explanation": "Response derived from compensation data... Sources: regional-uk.",
  "threadId": "059308c6-ea59-44bf-9524-b90bec4c363e"
}
```

## Deployment

Deployment is automated via GitHub Actions on push to `main`.

### Manual Deployment

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
aws s3 cp deployment.zip s3://spritz-agent-deployments-eu/agent-of-agreus/deployment.zip --region eu-west-2

aws lambda update-function-code \
  --function-name agent-of-agreus-dev \
  --s3-bucket spritz-agent-deployments-eu \
  --s3-key agent-of-agreus/deployment.zip \
  --region eu-west-2
```

### Required AWS Resources

1. **S3 Bucket**: `spritz-agent-deployments-eu` (eu-west-2)
2. **DynamoDB Table**: `agent-threads` with TTL on `ttl` attribute
3. **SSM Parameter**: `/app/agent-of-agreus/dev/ANTHROPIC_API_KEY`
4. **IAM Role**: Lambda execution role with SSM read + DynamoDB access

### Environment Variables

| Variable | Description |
|----------|-------------|
| `AGENT_NAME` | agent-of-agreus |
| `ENVIRONMENT` | dev |
| `THREADS_TABLE` | agent-threads |

## Testing

```bash
# Test discover
curl https://3odegxm7jolhdcyvvg7um3ws5m0zabtr.lambda-url.eu-west-2.on.aws/discover

# Test execute (new conversation)
curl -X POST "https://3odegxm7jolhdcyvvg7um3ws5m0zabtr.lambda-url.eu-west-2.on.aws/execute" \
  -H "Content-Type: application/json" \
  -d '{"inputs": [{"name": "payload", "data": "What is the average CEO salary in the UK?"}]}'

# Test thread continuity
curl -X POST "https://3odegxm7jolhdcyvvg7um3ws5m0zabtr.lambda-url.eu-west-2.on.aws/execute" \
  -H "Content-Type: application/json" \
  -d '{"inputs": [{"name": "payload", "data": "How does that compare to the USA?"}, {"name": "threadId", "data": "uuid-from-previous-response"}]}'
```

## Data Source

Based on the 2025 Agreus/KPMG Global Family Office Compensation Benchmark Report:
- 585 survey responses
- 20 qualitative interviews
- Coverage: UK, Europe, USA, Asia, Australia, Middle East
