# AWS Tag Compliance Checking Solution

Automated tag compliance solution using Claude Code + Amazon Bedrock as an AI agent. This solution monitors AWS resource creation events in real-time and validates that newly created resources comply with your organization's tagging policies.

## Overview

Cost allocation tags are critical for:
- **Cost Management**: Track and allocate AWS costs to projects, teams, or business units
- **Resource Organization**: Identify and manage resources across your AWS environment
- **Compliance**: Ensure all resources meet organizational tagging standards
- **Automation**: Enable tag-based automation for operations and security

This solution provides automated, real-time tag compliance checking with intelligent notifications powered by Amazon Bedrock's Claude models.

## Architecture

```
┌──────────────┐    ┌───────────────┐    ┌─────────────────────────┐    ┌──────────────────┐
│  CloudTrail  │───>│  EventBridge  │───>│  Lambda (Claude Code)   │───>│ Lark Notification│
│   (Events)   │    │    (Rules)    │    │  + Amazon Bedrock       │    │    (Alerts)      │
└──────────────┘    └───────────────┘    └───────────┬─────────────┘    └──────────────────┘
                                                     │
                                                     v
                                         ┌───────────────────────┐
                                         │  DynamoDB (Tag Rules) │
                                         └───────────────────────┘
```

### How It Works

1. **Event Capture**: CloudTrail logs all AWS API calls including resource creation events
2. **Event Filtering**: EventBridge rules filter for specific resource creation events (EC2, S3, RDS, etc.)
3. **Compliance Check**: Lambda function uses Claude Code with Amazon Bedrock to:
   - Fetch tag rules from DynamoDB
   - Analyze the created resource's tags
   - Determine compliance status
   - Generate human-readable compliance reports
4. **Notification**: Non-compliant resources trigger Lark/Feishu notifications with:
   - Resource details (ID, type, region)
   - Missing or invalid tags
   - Remediation guidance

## Features

- **Real-time Monitoring**: Instant detection of non-compliant resources
- **AI-Powered Analysis**: Claude models provide intelligent tag validation and recommendations
- **Flexible Rules**: Define custom tag requirements per resource type
- **Multi-Resource Support**: Monitor EC2, S3, RDS, Lambda, and more
- **Lark/Feishu Integration**: Native notification support for enterprise communication

## Alternative Architectures

This solution can be implemented using four different AWS approaches. Choose based on your complexity requirements and cost constraints.

### Current: Lambda + Claude Code (Interactive Mode)

```
EventBridge -> Lambda (Container) -> Claude Code (Bedrock) -> Lark Notification
                                          |
                                          v
                                    DynamoDB (Tag Rules)
```

**How It Works:**
- **Claude Code CLI** runs in interactive mode inside Lambda container
- Configured to use Bedrock for LLM access via IAM role
- Can leverage Claude Code's built-in capabilities (tools, memory) if needed
- Requires Docker container deployment

**Pricing (Estimated ~1000 events/day):**
| Component | Pricing | Monthly Cost |
|-----------|---------|--------------|
| Lambda | $0.0000166667/GB-sec | ~$1-2 (512MB, 30s avg) |
| Bedrock Claude Sonnet | $3/1M input, $15/1M output tokens | ~$2-5 (same as Direct API for single calls) |
| DynamoDB On-Demand | $1.25/million reads | ~$0.04 |
| ECR Storage | $0.10/GB/month | ~$0.05 |
| **Total** | | **~$3-8/month** |

**Note**: Bedrock token costs are **the same** as Direct API for single LLM calls.

**Pros:**
- Full Claude Code capabilities available (tools, memory, reasoning)
- Can handle complex multi-step tasks if needed
- Familiar Claude Code programming model
- Extensible with custom tools

**Cons:**
- **Larger Lambda**: Requires container image, longer cold starts
- **More resources**: Needs 512MB+ memory
- **Complex deployment**: Docker build required
- **May be overkill**: For simple single-call tasks, Direct API is simpler

---

### Option 1: Lambda + Bedrock InvokeModel API (Direct Calls)

```
EventBridge -> Lambda (Python) -> Bedrock InvokeModel API -> Lark Notification
                    |
                    v
              DynamoDB (Tag Rules)
```

**How It Works:**
- Lambda function directly calls Bedrock's `InvokeModel` API using boto3
- Simple Python code handles orchestration, tool execution, and notification
- No agent framework - just prompt/response calls
- Full control over prompt engineering and response handling

**Pricing (Estimated ~1000 events/day):**
| Component | Pricing | Monthly Cost |
|-----------|---------|--------------|
| Lambda | $0.0000166667/GB-sec | ~$0.50 (256MB, 30s avg) |
| Bedrock Claude Sonnet | $3/1M input, $15/1M output tokens | ~$2-5 |
| DynamoDB On-Demand | $1.25/million reads | ~$0.04 |
| **Total** | | **~$3-6/month** |

**Pros:**
- Simple architecture with full control
- **Lowest cost** for simple use cases
- No additional service overhead
- Faster cold starts (simple zip deployment)
- Lower memory requirements (256MB)

**Cons:**
- Manual orchestration code required
- No built-in agent capabilities (memory, tool management)
- Must implement retry logic and error handling manually
- Limited to simple prompt/response patterns

---

### Option 2: Amazon Bedrock Agents

```
EventBridge -> Lambda (Trigger) -> Bedrock Agent -> Action Group (Lambda) -> Lark Notification
                                        |
                                        v
                                  DynamoDB (Tag Rules)
```

**How It Works:**
- Pre-defined agent with action groups (tools)
- Agent automatically orchestrates: understanding request -> selecting tools -> executing -> responding
- Action groups backed by Lambda functions or OpenAPI schemas
- Built-in session management and conversation context

**Key Features:**
- **Managed orchestration**: Agent decides which tools to use
- **Action Groups**: Define tools via Lambda or OpenAPI (up to 5 tools per group)
- **Knowledge Bases**: Optional RAG for documentation lookup
- **Guardrails**: Built-in safety and content filtering
- **Session management**: Maintains conversation context

**Pricing (Estimated ~1000 events/day):**
| Component | Pricing | Monthly Cost |
|-----------|---------|--------------|
| Bedrock Agent Session | No additional fee | $0 |
| Bedrock Claude Sonnet | $3/1M input, $15/1M output tokens | ~$3-8 (more tokens) |
| Lambda (Trigger + Action) | $0.0000166667/GB-sec | ~$1 |
| DynamoDB On-Demand | $1.25/million reads | ~$0.04 |
| **Total** | | **~$4-10/month** |

**Pros:**
- Managed agent orchestration
- Built-in session management
- Native integration with AWS services
- Easier to add new tools/capabilities

**Cons:**
- ~20-50% more tokens consumed (agent system prompts)
- Slightly higher latency due to orchestration
- Less control over prompt engineering

**When to Use:**
- Multi-tool agents requiring orchestration
- Conversational interfaces
- Need for built-in session management

---

### Option 3: Amazon Bedrock AgentCore (Preview)

```
EventBridge -> AgentCore Runtime (Agent) -> AgentCore Gateway (Tools) -> Lark Notification
                      |                            |
                      v                            v
              AgentCore Memory              DynamoDB (Tag Rules)
```

**How It Works:**
- **AgentCore Runtime**: Secure, serverless hosting for AI agents (framework-agnostic)
- **AgentCore Gateway**: Transforms APIs/Lambda into agent-compatible tools, supports MCP
- **AgentCore Memory**: Short-term and long-term memory management
- **AgentCore Identity**: Secure access to AWS and third-party services
- **AgentCore Observability**: Tracing, debugging, monitoring

**Key Features:**
- **Framework Agnostic**: Works with LangGraph, Strands, CrewAI, custom frameworks
- **Any LLM**: Not limited to Bedrock models
- **MCP Support**: Model Context Protocol for tool integration
- **Session Isolation**: Each session runs in dedicated microVM
- **Long-running agents**: Supports up to 8-hour workloads
- **Consumption-based pricing**: Pay only for active CPU/memory usage

**Pricing (Estimated ~1000 events/day) - FREE in Preview until Sept 16, 2025:**
| Component | Pricing (after preview) | Monthly Cost |
|-----------|-------------------------|--------------|
| AgentCore Runtime | $0.00001389/vCPU-sec, $0.00000174/GB-sec | ~$2-5 |
| AgentCore Gateway | $0.01/1000 MCP operations | ~$0.30 |
| AgentCore Memory | $0.50/1M events (short-term) | ~$0.50 |
| Bedrock Claude Sonnet | $3/1M input, $15/1M output tokens | ~$3-8 |
| **Total** | | **~$6-14/month** |

**Pros:**
- Most flexible and powerful option
- Enterprise-grade features (observability, identity, memory)
- Framework agnostic - use any agent framework
- Better cost efficiency for I/O-heavy workloads
- Built-in MCP support for tool integration
- **Currently FREE during preview (until Sept 16, 2025)**

**Cons:**
- Most complex architecture
- Still in preview (GA expected late 2025)
- Higher operational complexity
- Overkill for simple use cases

**When to Use:**
- Building multiple agents that need to collaborate
- Long-running agent sessions (>15 minutes)
- Need to use non-Bedrock LLMs
- Enterprise requirements (observability, compliance, identity federation)
- Evaluating new technologies (free preview period)

---

### Option 4: Claude Agent SDK

```
EventBridge -> Lambda (Container) -> Claude Agent SDK -> Bedrock API -> Lark Notification
                                          |
                                          v
                                    DynamoDB (Tag Rules)
```

**How It Works:**
- **Claude Agent SDK** (Python/TypeScript) provides Claude Code capabilities as a library
- Built-in tools: Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch
- Supports Amazon Bedrock via `CLAUDE_CODE_USE_BEDROCK=1` environment variable
- Requires Claude Code CLI runtime installed in container

**Key Features:**
- **Built-in Tools**: File operations, bash commands, web search out of the box
- **Hooks**: Custom callbacks at agent lifecycle points
- **Subagents**: Spawn specialized agents for subtasks
- **MCP Support**: Model Context Protocol for external integrations
- **Sessions**: Maintain context across multiple exchanges

**Pricing (Estimated ~1000 events/day):**
| Component | Pricing | Monthly Cost |
|-----------|---------|--------------|
| Lambda | $0.0000166667/GB-sec | ~$2-4 (1GB+, container with Claude Code runtime) |
| Bedrock Claude Sonnet | $3/1M input, $15/1M output tokens | ~$2-5 |
| DynamoDB On-Demand | $1.25/million reads | ~$0.04 |
| ECR Storage | $0.10/GB/month | ~$0.10 (larger image) |
| **Total** | | **~$4-10/month** |

**Pros:**
- Rich built-in tools (file, bash, web operations)
- Hooks for custom behavior
- Subagent support for complex workflows
- Native MCP integration

**Cons:**
- **Requires Claude Code runtime** (large container ~1GB+)
- Claude models only (no other LLM providers)
- Higher Lambda memory requirements
- Designed for coding tasks, not event-driven processing
- **Not ideal for Lambda** - better suited for long-running processes

**When to Use:**
- Complex coding/development automation tasks
- When you need Claude Code's full capabilities programmatically
- CI/CD pipelines and development workflows
- NOT recommended for simple event-driven compliance checking

---

### Option 5: Strands Agents SDK (AWS Open Source)

```
EventBridge -> Lambda (Python) -> Strands Agent -> Bedrock API -> Lark Notification
                                       |
                                       v
                                 DynamoDB (Tag Rules)
```

**How It Works:**
- **Strands Agents SDK** is AWS's open-source framework for building AI agents
- Model-driven approach: LLM handles reasoning and planning
- Works with any LLM provider (Bedrock, OpenAI, Ollama, etc.)
- Native integration with Amazon Bedrock AgentCore

**Key Features:**
- **Model Agnostic**: Works with any LLM provider
- **Lightweight**: Minimal boilerplate, model handles orchestration
- **MCP Support**: Connect to external tools via Model Context Protocol
- **Multi-Agent**: Swarm, peer-to-peer, and supervisor patterns
- **Observability**: Built-in OpenTelemetry integration
- **A2A Protocol**: Agent-to-Agent communication support

**Pricing (Estimated ~1000 events/day):**
| Component | Pricing | Monthly Cost |
|-----------|---------|--------------|
| Lambda | $0.0000166667/GB-sec | ~$0.50-1 (256-512MB) |
| Bedrock Claude Sonnet | $3/1M input, $15/1M output tokens | ~$2-5 |
| DynamoDB On-Demand | $1.25/million reads | ~$0.04 |
| **Total** | | **~$3-7/month** |

**Installation:**
```bash
pip install strands-agents strands-agents-tools
```

**Pros:**
- **Native Lambda support** - designed for serverless
- Model agnostic (not locked to Claude)
- Lightweight, fast cold starts
- Native AgentCore integration
- Open source (Apache 2.0)
- Built-in observability

**Cons:**
- Fewer built-in tools (bring your own)
- Newer framework (less mature)
- Requires more custom tool implementation

**When to Use:**
- Serverless AI agents in Lambda
- Multi-agent systems
- When you need model flexibility (not just Claude)
- Production deployments with observability requirements

---

### Cost Comparison Summary

| Approach | Monthly Cost | Complexity | Lambda Fit | Best For |
|----------|--------------|------------|------------|----------|
| **Current: Claude Code** | $3-8 | Medium | Good | Flexible, scales to complex tasks |
| **Option 1: Direct API** | $3-6 | Low | Excellent | Simple, single-purpose checks |
| **Option 2: Bedrock Agents** | $4-10 | Medium | Good | Multi-tool, conversational |
| **Option 3: AgentCore** | $6-14 (FREE now) | High | Excellent | Multi-framework, enterprise |
| **Option 4: Claude Agent SDK** | $4-10 | High | Poor | Coding automation, CI/CD |
| **Option 5: Strands SDK** | $3-7 | Medium | Excellent | Serverless agents, multi-agent |

### Claude Code vs Direct API: Key Tradeoffs

| Factor | Claude Code (Current) | Direct API (Option 1) |
|--------|----------------------|----------------------|
| **Bedrock Token Cost** | **Same** | **Same** |
| **Lambda Cost** | Slightly higher (512MB) | Lower (256MB) |
| **Total Monthly** | ~$3-8 | ~$3-6 |
| **Cold Start** | Slower (container) | Faster (zip package) |
| **Deployment** | Docker build required | Simple Python zip |
| **Capabilities** | Full agent (tools, memory) | Simple prompts only |
| **Flexibility** | Can scale to complex tasks | Limited to simple tasks |

**Key Insight**: Bedrock token costs are **identical** for single LLM calls. The main cost difference (~$1-2/month) comes from Lambda resources (memory, container overhead), not Bedrock usage.

### Recommendation

For the **Tag Compliance Checking Solution**:

**Both Claude Code and Direct API are similarly priced** (~$1-2/month difference). Choose based on:

**Keep Claude Code (Current)** if:
- You want full agent capabilities available for future expansion
- You may need multi-step reasoning for complex compliance rules
- You prefer the Claude Code programming model
- Container deployment is acceptable

**Switch to Direct API (Option 1)** if:
- You prefer simpler deployment (zip vs Docker)
- You want faster cold starts
- You only need simple prompt/response patterns
- You want slightly lower Lambda costs

**Consider Option 2 (Bedrock Agents)** if:
- You plan to expand with multiple tools
- You need conversational capabilities
- You want AWS-managed agent orchestration

**Consider Option 3 (AgentCore)** if:
- You need enterprise features (observability, identity federation)
- You want to experiment during the free preview period (until Sept 2025)
- You're building multiple collaborating agents

**Avoid Option 4 (Claude Agent SDK)** for this use case:
- Requires Claude Code runtime (large container, slow cold starts)
- Designed for coding/development tasks, not event-driven processing
- Better suited for CI/CD pipelines and development automation

**Consider Option 5 (Strands Agents SDK)** if:
- You want a lightweight agent framework in Lambda
- You need model flexibility (not locked to Claude)
- You're building multi-agent systems
- You want built-in observability with OpenTelemetry

## Prerequisites

- AWS Account with Bedrock access (Claude models enabled in us-east-1)
- Lark/Feishu App credentials (Bot with messaging permissions)
- Go 1.21+ (for Pulumi infrastructure code)
- Pulumi CLI v3.x
- Python 3.12 (for Lambda function code)
- Docker (optional, for local testing)

### IAM Permissions Required

The deployment requires permissions to create:
- Lambda functions and execution roles
- EventBridge rules
- DynamoDB tables
- Secrets Manager secrets
- CloudWatch Logs
- Bedrock model invocation

## Dependencies

### Infrastructure (Go/Pulumi)

```go
// go.mod
require (
    github.com/pulumi/pulumi-aws/sdk/v6 v6.x.x
    github.com/pulumi/pulumi/sdk/v3 v3.x.x
)
```

### Lambda Function (Python 3.12)

```txt
# requirements.txt
boto3>=1.34.0
requests>=2.31.0
```

## Project Structure

```
.
├── infra/                    # Pulumi infrastructure (Go)
│   ├── main.go              # Main Pulumi program
│   ├── go.mod               # Go module definition
│   ├── go.sum               # Go dependencies
│   └── Pulumi.yaml          # Pulumi project configuration
├── lambda/                   # Lambda function (Python 3.12)
│   ├── handler.py           # Main Lambda handler
│   ├── tag_checker.py       # Tag compliance logic
│   ├── lark_notifier.py     # Lark notification client
│   ├── bedrock_client.py    # Amazon Bedrock integration
│   └── requirements.txt     # Python dependencies
└── README.md
```

## Deployment

### 1. Store Lark Credentials

Create a Lark/Feishu bot and store its credentials in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name tag-compliance/lark-credentials \
  --secret-string '{
    "appId": "YOUR_APP_ID",
    "appSecret": "YOUR_APP_SECRET",
    "chatId": "YOUR_CHAT_ID"
  }'
```

**Getting Lark Credentials:**
1. Go to [Lark Open Platform](https://open.larksuite.com/) or [Feishu Open Platform](https://open.feishu.cn/)
2. Create a new application
3. Enable Bot capabilities
4. Get the App ID and App Secret
5. Add the bot to a group chat and get the Chat ID

### 2. Deploy with Pulumi

```bash
cd infra
go mod tidy
pulumi login  # first time only, configure Pulumi backend
pulumi stack init dev  # create a new stack
pulumi up
```

**Pulumi Backend Options:**
- **Pulumi Cloud** (default): `pulumi login`
- **Local file**: `pulumi login --local`
- **S3 bucket**: `pulumi login s3://<bucket-name>`

### 3. Lambda Function Setup

The Lambda function is written in Python 3.12. Install dependencies:

```bash
cd lambda
pip install -r requirements.txt -t ./package
cd package && zip -r ../function.zip . && cd ..
zip function.zip handler.py
```

### 4. Configure Tag Rules

Add tag compliance rules to DynamoDB:

```bash
# Required tag: "site" must be "us" or "en"
aws dynamodb put-item \
  --table-name TagComplianceRules \
  --item '{
    "ruleId": {"S": "rule-001"},
    "tagKey": {"S": "site"},
    "allowedValues": {"L": [{"S": "us"}, {"S": "en"}]},
    "enabled": {"BOOL": true}
  }'

# Required tag: "environment" must be "dev", "staging", or "prod"
aws dynamodb put-item \
  --table-name TagComplianceRules \
  --item '{
    "ruleId": {"S": "rule-002"},
    "tagKey": {"S": "environment"},
    "allowedValues": {"L": [{"S": "dev"}, {"S": "staging"}, {"S": "prod"}]},
    "enabled": {"BOOL": true}
  }'

# Required tag: "cost-center" (any value allowed)
aws dynamodb put-item \
  --table-name TagComplianceRules \
  --item '{
    "ruleId": {"S": "rule-003"},
    "tagKey": {"S": "cost-center"},
    "allowedValues": {"L": []},
    "enabled": {"BOOL": true}
  }'
```

## Tag Rule Schema

| Field | Type | Description |
|-------|------|-------------|
| `ruleId` | String | Unique identifier for the rule |
| `tagKey` | String | The tag key that must be present |
| `allowedValues` | List | Allowed values for the tag (empty list = any value) |
| `enabled` | Boolean | Whether the rule is active |
| `resourceTypes` | List (optional) | Specific resource types to apply rule to |
| `description` | String (optional) | Human-readable description of the rule |

## Testing

### Trigger a Compliance Violation

Create an EC2 instance without required tags:

```bash
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t2.micro \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=test-instance}]'
```

This should trigger a Lark notification because the "site" tag is missing.

### Create a Compliant Resource

```bash
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t2.micro \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=compliant-instance},{Key=site,Value=us},{Key=environment,Value=dev},{Key=cost-center,Value=engineering}]'
```

## Supported Resource Types

- EC2 Instances
- S3 Buckets
- RDS Instances
- Lambda Functions
- EBS Volumes
- VPCs and Subnets
- Load Balancers
- Auto Scaling Groups

## Configuration Options

### Pulumi Configuration

Set stack-specific configuration:

```bash
pulumi config set aws:region us-east-1
pulumi config set tagCompliance:bedrockModelId anthropic.claude-3-sonnet-20240229-v1:0
pulumi config set tagCompliance:larkSecretName tag-compliance/lark-credentials
```

### Lambda Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_MODEL_ID` | Claude model to use | `anthropic.claude-3-sonnet-20240229-v1:0` |
| `RULES_TABLE_NAME` | DynamoDB table name | `TagComplianceRules` |
| `LARK_SECRET_NAME` | Secrets Manager secret name | `tag-compliance/lark-credentials` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `PYTHONPATH` | Python module path | `/var/task` |

### Lambda Runtime

- **Runtime**: Python 3.12
- **Architecture**: arm64 (Graviton2) for cost optimization
- **Memory**: 256 MB (recommended)
- **Timeout**: 60 seconds

## Local Development

### Testing Lambda Locally

```bash
cd lambda
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run unit tests
python -m pytest tests/

# Test with sample event
python -c "from handler import lambda_handler; lambda_handler({'test': 'event'}, None)"
```

### Pulumi Preview

Preview infrastructure changes before deploying:

```bash
cd infra
pulumi preview
```

### Destroy Infrastructure

```bash
cd infra
pulumi destroy
```

## Troubleshooting

### No Notifications Received

1. Check CloudWatch Logs for the Lambda function
2. Verify EventBridge rule is enabled
3. Confirm Lark bot has messaging permissions
4. Ensure the bot is added to the target chat

### Lambda Timeout

- Increase Lambda timeout (default: 30s, recommended: 60s)
- Check Bedrock model availability in your region

### Permission Errors

- Verify Lambda execution role has Bedrock invoke permissions
- Check Secrets Manager access permissions
- Ensure DynamoDB read permissions are granted

### Pulumi Issues

- **State lock**: `pulumi cancel` to cancel a stuck operation
- **Stack not found**: `pulumi stack select <stack-name>`
- **AWS credentials**: Ensure `AWS_PROFILE` or credentials are configured

## Cost Considerations

- **Lambda**: Pay per invocation and duration
- **Bedrock**: Pay per token (input + output)
- **DynamoDB**: On-demand pricing for reads
- **EventBridge**: Free for first 1 million events/month
- **Secrets Manager**: $0.40/secret/month

Estimated cost for moderate usage (~1000 resources/day): $5-15/month

## Security Best Practices

1. Use least-privilege IAM policies
2. Enable VPC endpoints for Bedrock and DynamoDB (optional)
3. Encrypt DynamoDB table at rest
4. Rotate Lark credentials regularly
5. Enable CloudTrail logging for audit

## License

MIT License
