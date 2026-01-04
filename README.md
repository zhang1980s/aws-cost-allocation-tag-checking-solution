# AWS Tag Compliance Checking Solution

Automated tag compliance solution using **Strands Agents SDK** + Amazon Bedrock as an AI agent. This solution monitors AWS resource creation events in real-time and validates that newly created resources comply with your organization's tagging policies.

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
│  CloudTrail  │───>│  EventBridge  │───>│  Lambda (Strands Agent) │───>│ Lark Notification│
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
3. **Compliance Check**: Lambda function uses Strands Agents SDK with Amazon Bedrock to:
   - Fetch tag rules from DynamoDB
   - Analyze the created resource's tags using AI-powered reasoning
   - Determine compliance status
   - Generate human-readable compliance reports
4. **Notification**: Non-compliant resources trigger Lark/Feishu notifications with:
   - Resource details (ID, type, region)
   - Missing or invalid tags
   - Remediation guidance

## Features

- **Real-time Monitoring**: Instant detection of non-compliant resources
- **AI-Powered Analysis**: Amazon Bedrock models provide intelligent tag validation and recommendations
- **Flexible Rules**: Define custom tag requirements per resource type
- **Multi-Resource Support**: Monitor EC2, S3, RDS, Lambda, and more
- **Lark/Feishu Integration**: Native notification support for enterprise communication
- **Model Flexibility**: Support for multiple Bedrock models (Claude, Nova)

## Recommended Models

This solution supports multiple Amazon Bedrock models. Choose based on your cost and capability requirements.

### Model Comparison

| Model | Model ID | Input/1M tokens | Output/1M tokens | Best For |
|-------|----------|-----------------|------------------|----------|
| **Claude Haiku 4.5** | `anthropic.claude-haiku-4-5-20251001-v1:0` | ~$0.80 | ~$4.00 | Cost optimization, fast responses |
| **Amazon Nova 2 Lite** | `amazon.nova-2-lite-v1:0` | ~$0.04 | ~$0.16 | Lowest cost, extended thinking |
| Claude Sonnet 4.5 | `anthropic.claude-sonnet-4-5-20250929-v1:0` | ~$3.00 | ~$15.00 | Complex analysis, highest accuracy |

> **Note**: Amazon Nova 2 Pro is in preview. Use Nova 2 Lite for production workloads until Nova 2 Pro is generally available.

### Claude Haiku 4.5 (Recommended for Balance)

```bash
# Model ID
anthropic.claude-haiku-4-5-20251001-v1:0
```

- **Pricing**: ~$0.80/1M input, ~$4.00/1M output tokens
- **Savings**: ~70% cheaper than Claude Sonnet 4.5
- **Features**: Vision support, extended thinking, near-frontier performance
- **Regions**: Global cross-region inference (multiple regions)
- **Best for**: Tag compliance checks requiring good reasoning at lower cost

### Amazon Nova 2 Lite (Recommended for Cost)

```bash
# Model ID
amazon.nova-2-lite-v1:0
```

- **Pricing**: ~$0.04/1M input, ~$0.16/1M output tokens
- **Savings**: ~99% cheaper than Claude Sonnet 4.5
- **Features**: Extended thinking, 1M context window, code interpreter, web grounding
- **Regions**: Global cross-region inference (multiple regions)
- **Best for**: Simple tag checks, high-volume workloads, maximum cost savings

### Claude Sonnet 4.5 (Premium)

```bash
# Model ID
anthropic.claude-sonnet-4-5-20250929-v1:0
```

- **Pricing**: ~$3/1M input, ~$15/1M output tokens
- **Features**: Frontier performance, extended thinking, vision, hybrid reasoning
- **Regions**: Global cross-region inference (multiple regions)
- **Best for**: Complex analysis requiring highest accuracy

### Cost Savings Example

For ~1000 tag compliance events/day (~30,000/month):

| Model | Est. Monthly Bedrock Cost | Savings |
|-------|---------------------------|---------|
| Claude Sonnet 4.5 | ~$2-5/month | baseline |
| Claude Haiku 4.5 | ~$0.50-1.50/month | ~70-75% |
| Amazon Nova 2 Lite | ~$0.05-0.20/month | ~95-99% |

**Recommendation**: Start with **Amazon Nova 2 Lite** for maximum cost savings. Use **Claude Haiku 4.5** if you need better reasoning capabilities.

## Alternative Architectures

This solution can be implemented using several different approaches. The current implementation uses **Strands Agents SDK**. Other options are listed below for reference.

### Current: Lambda + Strands Agents SDK (AWS Open Source)

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
- Lightweight deployment with simple Python zip package

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
- Built-in observability with OpenTelemetry

**Cons:**
- Fewer built-in tools (bring your own)
- Newer framework (less mature)
- Requires more custom tool implementation

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

### Option 5: Lambda + Claude Code (Interactive Mode)

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
| Bedrock Claude Sonnet | $3/1M input, $15/1M output tokens | ~$2-5 |
| DynamoDB On-Demand | $1.25/million reads | ~$0.04 |
| ECR Storage | $0.10/GB/month | ~$0.05 |
| **Total** | | **~$3-8/month** |

**Pros:**
- Full Claude Code capabilities available (tools, memory, reasoning)
- Can handle complex multi-step tasks if needed
- Familiar Claude Code programming model
- Extensible with custom tools

**Cons:**
- **Larger Lambda**: Requires container image, longer cold starts
- **More resources**: Needs 512MB+ memory
- **Complex deployment**: Docker build required
- **May be overkill**: For simple single-call tasks

**When to Use:**
- Complex multi-step tasks requiring full agent capabilities
- When you need Claude Code's built-in tools
- Container deployment is acceptable

---

### Option 6: LangGraph + Amazon Bedrock

```
EventBridge -> Lambda (Python) -> LangGraph Agent -> Bedrock API -> Lark Notification
                                       |
                                       v
                                 DynamoDB (Tag Rules)
```

**How It Works:**
- **LangGraph** is an open-source orchestration framework from LangChain for building stateful, multi-agent systems
- Uses graph-based architecture: **Nodes** (functions), **Edges** (transitions), **State** (shared data)
- Integrates with Amazon Bedrock via `langchain-aws` package's `ChatBedrock` class
- Supports checkpointing for durable execution and recovery from failures

**Key Features:**
- **Graph-Based Orchestration**: Model workflows as directed graphs with conditional routing
- **State Management**: Shared state across nodes with persistence via checkpoints
- **Memory**: Both short-term (session) and long-term (cross-session) memory
- **Human-in-the-Loop**: Built-in support for interrupts and human approval
- **Durable Execution**: Resume from failures, time-travel debugging
- **Multi-Agent Patterns**: Supervisor, swarm, and peer-to-peer collaboration

**Bedrock Integration:**
```python
from langchain_aws import ChatBedrock
from langgraph.graph import StateGraph

# Initialize Bedrock-backed LLM
llm = ChatBedrock(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    region_name="us-east-1"
)

# Build graph with nodes and edges
graph = StateGraph(AgentState)
graph.add_node("check_tags", check_tags_node)
graph.add_node("notify", notify_node)
graph.add_edge("check_tags", "notify")
```

**Pricing (Estimated ~1000 events/day):**
| Component | Pricing | Monthly Cost |
|-----------|---------|--------------|
| Lambda | $0.0000166667/GB-sec | ~$1-2 (512MB, 30s avg) |
| Bedrock Claude Sonnet | $3/1M input, $15/1M output tokens | ~$2-5 |
| DynamoDB On-Demand | $1.25/million reads | ~$0.04 |
| **Total** | | **~$3-8/month** |

**Installation:**
```bash
pip install langgraph langchain-aws langchain-core
```

**Pros:**
- **Powerful orchestration**: Graph-based workflows with conditional branching
- **Open source**: Apache 2.0 license, active community (LangChain ecosystem)
- **Amazon Bedrock integration**: Native support via `langchain-aws`
- **Durable execution**: Checkpointing for fault tolerance
- **Multi-agent ready**: Built-in patterns for agent collaboration
- **LangSmith integration**: Observability and debugging tools
- **AgentCore compatible**: Can deploy to AgentCore Runtime if needed

**Cons:**
- **Larger dependency footprint**: LangChain ecosystem adds ~50MB+ to deployment
- **Cold start impact**: More dependencies = longer cold starts (~3-5s)
- **Learning curve**: Graph concepts require understanding
- **Overkill for simple tasks**: Best for complex multi-step workflows
- **State persistence**: Requires external storage (DynamoDB, Redis) for checkpoints

**When to Use:**
- Complex multi-step compliance workflows
- Multi-agent systems with supervisor coordination
- Workflows requiring human approval (human-in-the-loop)
- Need for durable execution with failure recovery
- Already using LangChain ecosystem
- Planning to scale to AgentCore Runtime later

---

### Cost Comparison Summary

| Approach | Monthly Cost | Complexity | Lambda Fit | Best For |
|----------|--------------|------------|------------|----------|
| **Current: Strands SDK** | $3-7 | Medium | Excellent | Serverless agents, multi-agent |
| **Option 1: Direct API** | $3-6 | Low | Excellent | Simple, single-purpose checks |
| **Option 2: Bedrock Agents** | $4-10 | Medium | Good | Multi-tool, conversational |
| **Option 3: AgentCore** | $6-14 (FREE now) | High | Excellent | Multi-framework, enterprise |
| **Option 4: Claude Agent SDK** | $4-10 | High | Poor | Coding automation, CI/CD |
| **Option 5: Claude Code** | $3-8 | Medium | Good | Full agent capabilities |
| **Option 6: LangGraph** | $3-8 | Medium-High | Good | Graph workflows, multi-agent |

### Strands SDK vs Direct API: Key Tradeoffs

| Factor | Strands SDK (Current) | Direct API (Option 1) |
|--------|----------------------|----------------------|
| **Bedrock Token Cost** | **Same** | **Same** |
| **Lambda Cost** | ~$0.50-1 (256-512MB) | ~$0.50 (256MB) |
| **Total Monthly** | ~$3-7 | ~$3-6 |
| **Cold Start** | Fast (zip package) | Fastest (minimal deps) |
| **Deployment** | Simple Python zip | Simple Python zip |
| **Capabilities** | Agent framework (tools, multi-agent) | Simple prompts only |
| **Model Flexibility** | Any LLM provider | Bedrock only |
| **Observability** | Built-in OpenTelemetry | Manual implementation |

**Key Insight**: Strands SDK provides agent capabilities with minimal overhead. It's the best balance of features and Lambda fit for this use case.

### Recommendation

For the **Tag Compliance Checking Solution**, we chose **Strands Agents SDK** as the implementation because:

**Why Strands SDK (Current Choice):**
- **Native Lambda support** - designed for serverless from the ground up
- **Model agnostic** - not locked to Claude, can switch LLM providers
- **Lightweight** - fast cold starts, minimal dependencies
- **Built-in observability** - OpenTelemetry integration out of the box
- **Open source** - Apache 2.0 license, active AWS support
- **AgentCore ready** - can scale to AgentCore Runtime if needed

**Alternative Options:**

**Consider Option 1 (Direct API)** if:
- You only need simple prompt/response patterns
- You want the absolute minimum dependencies
- You don't need agent framework features

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

**Consider Option 5 (Claude Code)** if:
- You need Claude Code's full built-in capabilities
- Container deployment is acceptable
- You're familiar with Claude Code programming model

**Consider Option 6 (LangGraph)** if:
- You need complex graph-based workflows with conditional branching
- You want multi-agent systems with supervisor patterns
- You're already using LangChain ecosystem

## Prerequisites

- AWS Account with Bedrock access (Claude models enabled in us-east-1)
- Lark/Feishu App credentials (Bot with messaging permissions)
- Go 1.24+ (for Pulumi infrastructure code)
- Pulumi CLI v3.x
- Python 3.12 (for Lambda function code)

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
strands-agents>=0.1.0
strands-agents-tools>=0.1.0
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
│   ├── agent.py             # Strands Agent definition
│   ├── tools/               # Custom agent tools
│   │   ├── __init__.py
│   │   ├── tag_checker.py   # Tag compliance checking tool
│   │   ├── dynamodb_rules.py # DynamoDB rules fetcher tool
│   │   └── lark_notifier.py # Lark notification tool
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

The Lambda function is written in Python 3.12 using Strands Agents SDK. Install dependencies:

```bash
cd lambda
pip install -r requirements.txt -t ./package
cd package && zip -r ../function.zip . && cd ..
zip -g function.zip handler.py agent.py
zip -gr function.zip tools/
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
pulumi config set tagCompliance:larkSecretName tag-compliance/lark-credentials

# Choose ONE of the following models:

# Option 1: Amazon Nova 2 Lite (Recommended - lowest cost, ~99% savings)
pulumi config set tagCompliance:bedrockModelId amazon.nova-2-lite-v1:0

# Option 2: Claude Haiku 4.5 (best balance of cost and capability)
pulumi config set tagCompliance:bedrockModelId anthropic.claude-haiku-4-5-20251001-v1:0

# Option 3: Claude Sonnet 4.5 (highest accuracy, premium pricing)
pulumi config set tagCompliance:bedrockModelId anthropic.claude-sonnet-4-5-20250929-v1:0
```

### Lambda Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_MODEL_ID` | Bedrock model to use (see [Recommended Models](#recommended-models)) | `amazon.nova-2-lite-v1:0` |
| `RULES_TABLE_NAME` | DynamoDB table name | `TagComplianceRules` |
| `LARK_SECRET_NAME` | Secrets Manager secret name | `tag-compliance/lark-credentials` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `PYTHONPATH` | Python module path | `/var/task` |

**Supported Model IDs:**
- `amazon.nova-2-lite-v1:0` - Amazon Nova 2 Lite (recommended for cost)
- `anthropic.claude-haiku-4-5-20251001-v1:0` - Claude Haiku 4.5 (recommended for balance)
- `anthropic.claude-sonnet-4-5-20250929-v1:0` - Claude Sonnet 4.5 (premium)

### Lambda Runtime

| Setting | Value | Notes |
|---------|-------|-------|
| **Runtime** | Python 3.12 | Based on Amazon Linux 2023 (AL2023) |
| **Base OS** | Amazon Linux 2023 | Uses `microdnf` package manager (not `yum`) |
| **Architecture** | arm64 (Graviton) | ~20% better price-performance vs x86_64 |
| **Memory** | 256-512 MB | Recommended for Strands Agents |
| **Timeout** | 60 seconds | Adjust based on model response time |
| **Framework** | Strands Agents SDK | AWS open-source agent framework |

**Why Amazon Linux 2023 + ARM64?**
- **AL2023**: Smaller container image, improved security, latest packages
- **ARM64 (Graviton)**: Up to 20% better price-performance compared to x86_64
- **Python 3.12**: Latest stable Python with performance improvements

```bash
# Pulumi example for ARM64 Lambda
pulumi config set tagCompliance:lambdaArchitecture arm64
```

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
- **Bedrock**: Pay per token (input + output) - see [Recommended Models](#recommended-models)
- **DynamoDB**: On-demand pricing for reads
- **EventBridge**: Free for first 1 million events/month
- **Secrets Manager**: $0.40/secret/month

### Estimated Monthly Cost by Model (~1000 resources/day)

| Model | Lambda | Bedrock | Other | Total |
|-------|--------|---------|-------|-------|
| Amazon Nova 2 Lite | ~$0.50-1 | ~$0.05-0.20 | ~$0.50 | **~$1-2/month** |
| Claude Haiku 4.5 | ~$0.50-1 | ~$0.50-1.50 | ~$0.50 | **~$1.50-3/month** |
| Claude Sonnet 4.5 | ~$0.50-1 | ~$2-5 | ~$0.50 | **~$3-7/month** |

**Tip**: Use **Amazon Nova 2 Lite** for maximum cost savings (up to 95% reduction on Bedrock costs).

## Security Best Practices

1. Use least-privilege IAM policies
2. Enable VPC endpoints for Bedrock and DynamoDB (optional)
3. Encrypt DynamoDB table at rest
4. Rotate Lark credentials regularly
5. Enable CloudTrail logging for audit

## License

MIT License
