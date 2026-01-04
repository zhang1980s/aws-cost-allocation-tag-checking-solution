"""Unit tests for the agent module."""

import pytest
from unittest.mock import patch, MagicMock

from agent import TagComplianceAgent, SYSTEM_PROMPT


class TestTagComplianceAgent:
    """Tests for TagComplianceAgent class."""

    @patch("agent.Agent")
    @patch("agent.BedrockModel")
    def test_agent_initialization(self, mock_bedrock_model, mock_agent):
        """Test agent initializes with correct parameters."""
        mock_model_instance = MagicMock()
        mock_bedrock_model.return_value = mock_model_instance

        agent = TagComplianceAgent()

        # Verify Bedrock model was initialized
        mock_bedrock_model.assert_called_once_with(
            model_id="amazon.nova-2-lite-v1:0",
            region_name="us-east-1",
        )

        # Verify Agent was initialized with model and tools
        mock_agent.assert_called_once()
        call_kwargs = mock_agent.call_args[1]
        assert call_kwargs["model"] == mock_model_instance
        assert call_kwargs["system_prompt"] == SYSTEM_PROMPT
        assert len(call_kwargs["tools"]) == 4  # 4 tools defined

    @patch("agent.Agent")
    @patch("agent.BedrockModel")
    def test_agent_uses_env_model_id(self, mock_bedrock_model, mock_agent):
        """Test agent uses model ID from environment."""
        import os
        os.environ["BEDROCK_MODEL_ID"] = "anthropic.claude-haiku-4-5-20251001-v1:0"

        TagComplianceAgent()

        mock_bedrock_model.assert_called_once()
        call_kwargs = mock_bedrock_model.call_args[1]
        assert call_kwargs["model_id"] == "anthropic.claude-haiku-4-5-20251001-v1:0"

        # Reset
        os.environ["BEDROCK_MODEL_ID"] = "amazon.nova-2-lite-v1:0"

    @patch("agent.Agent")
    @patch("agent.BedrockModel")
    def test_check_compliance_success(self, mock_bedrock_model, mock_agent):
        """Test successful compliance check."""
        mock_agent_instance = MagicMock()
        mock_agent.return_value = mock_agent_instance
        mock_agent_instance.return_value = "Resource is compliant. All required tags present."

        agent = TagComplianceAgent()
        result = agent.check_compliance({
            "resource_type": "ec2:instance",
            "resource_ids": ["i-1234567890abcdef0"],
            "region": "us-east-1",
            "account_id": "123456789012",
            "tags": [
                {"Key": "site", "Value": "us"},
                {"Key": "environment", "Value": "dev"},
            ],
            "event_time": "2024-01-15T10:30:00Z",
            "user_identity": {"arn": "arn:aws:iam::123456789012:user/admin"},
        })

        assert result["status"] == "completed"
        assert result["resource_type"] == "ec2:instance"
        assert result["resource_ids"] == ["i-1234567890abcdef0"]
        assert "compliant" in result["analysis"].lower()

    @patch("agent.Agent")
    @patch("agent.BedrockModel")
    def test_check_compliance_error(self, mock_bedrock_model, mock_agent):
        """Test compliance check error handling."""
        mock_agent_instance = MagicMock()
        mock_agent.return_value = mock_agent_instance
        mock_agent_instance.side_effect = Exception("Bedrock API error")

        agent = TagComplianceAgent()
        result = agent.check_compliance({
            "resource_type": "ec2:instance",
            "resource_ids": ["i-123"],
            "region": "us-east-1",
            "account_id": "123456789012",
        })

        assert result["status"] == "error"
        assert "Bedrock API error" in result["error"]

    @patch("agent.Agent")
    @patch("agent.BedrockModel")
    def test_format_compliance_prompt(self, mock_bedrock_model, mock_agent):
        """Test prompt formatting."""
        agent = TagComplianceAgent()

        resource_info = {
            "resource_type": "s3:bucket",
            "resource_ids": ["my-test-bucket"],
            "region": "us-west-2",
            "account_id": "123456789012",
            "tags": [
                {"Key": "environment", "Value": "prod"},
            ],
            "event_time": "2024-01-15T10:30:00Z",
            "user_identity": {"arn": "arn:aws:iam::123456789012:role/Admin"},
        }

        prompt = agent._format_compliance_prompt(resource_info)

        assert "s3:bucket" in prompt
        assert "my-test-bucket" in prompt
        assert "us-west-2" in prompt
        assert "123456789012" in prompt
        assert "environment=prod" in prompt
        assert "Admin" in prompt

    @patch("agent.Agent")
    @patch("agent.BedrockModel")
    def test_format_prompt_no_tags(self, mock_bedrock_model, mock_agent):
        """Test prompt formatting with no tags."""
        agent = TagComplianceAgent()

        resource_info = {
            "resource_type": "ec2:instance",
            "resource_ids": ["i-123"],
            "region": "us-east-1",
            "account_id": "123456789012",
            "tags": [],
            "event_time": "2024-01-15T10:30:00Z",
            "user_identity": {},
        }

        prompt = agent._format_compliance_prompt(resource_info)

        assert "No tags provided" in prompt

    @patch("agent.Agent")
    @patch("agent.BedrockModel")
    def test_format_prompt_unknown_creator(self, mock_bedrock_model, mock_agent):
        """Test prompt formatting with unknown creator."""
        agent = TagComplianceAgent()

        resource_info = {
            "resource_type": "ec2:instance",
            "resource_ids": ["i-123"],
            "region": "us-east-1",
            "account_id": "123456789012",
            "tags": [],
            "user_identity": {},  # No arn or userName
        }

        prompt = agent._format_compliance_prompt(resource_info)

        assert "Unknown" in prompt


class TestSystemPrompt:
    """Tests for the system prompt."""

    def test_system_prompt_contains_instructions(self):
        """Test that system prompt contains key instructions."""
        assert "get_tag_rules" in SYSTEM_PROMPT
        assert "check_resource_tags" in SYSTEM_PROMPT
        assert "send_sns_notification" in SYSTEM_PROMPT
        assert "DynamoDB" in SYSTEM_PROMPT

    def test_system_prompt_defines_workflow(self):
        """Test that system prompt defines the compliance workflow."""
        # Should mention the key steps
        assert "retrieve" in SYSTEM_PROMPT.lower() or "fetch" in SYSTEM_PROMPT.lower()
        assert "validate" in SYSTEM_PROMPT.lower() or "check" in SYSTEM_PROMPT.lower()
        assert "notification" in SYSTEM_PROMPT.lower() or "alert" in SYSTEM_PROMPT.lower()
