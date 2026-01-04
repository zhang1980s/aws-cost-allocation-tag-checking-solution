# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AWS Tag Compliance Checking Solution - An event-driven serverless application that monitors AWS resource creation and validates tag compliance using AI-powered analysis via Amazon Bedrock.

## Architecture

```
CloudTrail → EventBridge → Lambda (Strands Agent + Bedrock) → Lark Notification
                                    ↓
                              DynamoDB (Tag Rules)
```

## Tech Stack

- **Infrastructure**: Pulumi with Go 1.24+ (`infra/`)
- **Lambda Runtime**: Python 3.12 on Amazon Linux 2023, ARM64 (Graviton)
- **Agent Framework**: Strands Agents SDK
- **LLM Provider**: Amazon Bedrock (Nova 2 Lite, Claude Haiku 4.5, Claude Sonnet 4.5)
- **Storage**: DynamoDB (tag rules)
- **Notifications**: Lark/Feishu Bot API

## Common Commands

### Infrastructure (Pulumi/Go)

```bash
cd infra
go mod tidy                    # Install Go dependencies
pulumi preview                 # Preview changes
pulumi up                      # Deploy infrastructure
pulumi destroy                 # Tear down infrastructure
pulumi config set <key> <val>  # Set configuration
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
infra/              # Pulumi infrastructure (Go)
  main.go           # Main Pulumi program
  Pulumi.yaml       # Project configuration

lambda/             # Lambda function (Python 3.12)
  handler.py        # Lambda entry point
  agent.py          # Strands Agent definition
  tools/            # Custom agent tools
    tag_checker.py
    dynamodb_rules.py
    lark_notifier.py
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
- `LARK_SECRET_NAME` - Secrets Manager secret for Lark credentials

### Pulumi Config Keys

```bash
pulumi config set aws:region us-east-1
pulumi config set tagCompliance:bedrockModelId amazon.nova-2-lite-v1:0
pulumi config set tagCompliance:larkSecretName tag-compliance/lark-credentials
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
