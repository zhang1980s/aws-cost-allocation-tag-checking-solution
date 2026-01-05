# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AWS Tag Compliance Checking Solution - An event-driven serverless application that monitors AWS resource creation and validates tag compliance using AI-powered analysis via Amazon Bedrock.

## Architecture

Supports **multi-account/multi-region** deployments using hub-and-spoke pattern.

### Single Account (Hub Mode)
```
CloudTrail → EventBridge (Custom Bus) → Lambda (Strands Agent + Bedrock) → SNS Topic
                                              ↓
                                        DynamoDB (Tag Rules)
```

### Multi-Account (Hub-and-Spoke)
```
Spoke Accounts (any region):
  CloudTrail → EventBridge → Forward to Hub
                    ↓
Hub Account:
  EventBridge (Custom Bus) → Lambda → SNS Topic
                               ↓
                         DynamoDB (Tag Rules)
```

## Tech Stack

- **Infrastructure**: Pulumi with Go 1.24+ (`infra/`)
- **Lambda Runtime**: Python 3.12 on Amazon Linux 2023, ARM64 (Graviton)
- **Agent Framework**: Strands Agents SDK
- **LLM Provider**: Amazon Bedrock (Nova 2 Lite, Claude Haiku 4.5, Claude Sonnet 4.5)
- **Storage**: DynamoDB (tag rules)
- **Notifications**: Amazon SNS (supports Email, SMS, Slack, webhooks)

## Common Commands

### Infrastructure (Pulumi/Go)

```bash
# Hub account (central processing)
cd infra/hub
go mod tidy                    # Install Go dependencies
pulumi stack init prod         # Create stack
pulumi config set hub:spokeAccountIds "111111,222222"  # Optional: allow spoke accounts
pulumi up                      # Deploy hub infrastructure

# Spoke account (event forwarding)
cd infra/spoke
go mod tidy
pulumi stack init <account>-<region>
pulumi config set spoke:hubAccountId 000000000000
pulumi config set spoke:hubRegion us-east-1
pulumi config set spoke:hubEventBusArn arn:aws:events:us-east-1:000000000000:event-bus/tag-compliance-events
pulumi up                      # Deploy spoke infrastructure
```

### Lambda (Python)

```bash
cd lambda
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Package for deployment
pip install -r requirements.txt -t ./package
cd package && zip -r ../function.zip . && cd ..
zip -g function.zip handler.py agent.py
zip -gr function.zip tools/

# Run tests
python -m pytest tests/
```

## Project Structure

```
infra/
  hub/              # Hub account stack (deploy once)
    main.go         # Lambda, DynamoDB, SNS, EventBridge bus
    Pulumi.yaml     # Hub configuration
  spoke/            # Spoke account stack (deploy per account/region)
    main.go         # EventBridge forwarding rule
    Pulumi.yaml     # Spoke configuration

lambda/             # Lambda function (Python 3.12)
  handler.py        # Lambda entry point
  agent.py          # Strands Agent definition
  tools/            # Custom agent tools
    tag_checker.py
    dynamodb_rules.py
    sns_notifier.py
```

## Key Configuration

### Bedrock Model IDs (choose one)

| Model | Model ID | Use Case |
|-------|----------|----------|
| Nova 2 Lite | `amazon.nova-2-lite-v1:0` | Lowest cost (~99% savings) |
| Claude Haiku 4.5 | `anthropic.claude-haiku-4-5-20251001-v1:0` | Balance of cost/capability |
| Claude Sonnet 4.5 | `anthropic.claude-sonnet-4-5-20250929-v1:0` | Highest accuracy |

### Lambda Environment Variables

- `BEDROCK_MODEL_ID` - Model to use (default: `amazon.nova-2-lite-v1:0`)
- `RULES_TABLE_NAME` - DynamoDB table (default: `TagComplianceRules`)
- `SNS_TOPIC_ARN` - SNS topic ARN for notifications

### Pulumi Config Keys

```bash
# Deployment mode (hub or spoke)
pulumi config set tagCompliance:deploymentMode hub

# Hub mode - specify allowed spoke accounts
pulumi config set tagCompliance:spokeAccountIds "111111111111,222222222222"

# Spoke mode - specify hub account details
pulumi config set tagCompliance:hubAccountId 000000000000
pulumi config set tagCompliance:hubRegion us-east-1
pulumi config set tagCompliance:hubEventBusArn arn:aws:events:us-east-1:000000000000:event-bus/tag-compliance-events

# Common configuration
pulumi config set aws:region us-east-1
pulumi config set tagCompliance:bedrockModelId amazon.nova-2-lite-v1:0
pulumi config set tagCompliance:lambdaArchitecture arm64
```

## DynamoDB Tag Rule Schema

```json
{
  "ruleId": "string",
  "tagKey": "string",
  "allowedValues": ["string"],
  "enabled": true,
  "resourceTypes": ["optional"],
  "description": "optional"
}
```

## Lambda Runtime Details

- **Python**: 3.12 (based on Amazon Linux 2023)
- **Architecture**: arm64 (Graviton) - 20% better price-performance
- **Memory**: 256-512 MB
- **Timeout**: 60 seconds
- **Package Manager**: `microdnf` (not `yum`)
