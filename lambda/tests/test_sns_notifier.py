"""Unit tests for the sns_notifier tool module."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from tools.sns_notifier import (
    send_sns_notification,
    _build_notification_message,
    _build_sms_message,
)


class TestBuildNotificationMessage:
    """Tests for _build_notification_message function."""

    def test_build_message_with_missing_tags(self):
        """Test message building with missing tags."""
        message = _build_notification_message(
            resource_type="ec2:instance",
            resource_ids=["i-1234567890abcdef0"],
            region="us-east-1",
            account_id="123456789012",
            missing_tags=["site", "cost-center"],
            invalid_values=[],
            creator="arn:aws:iam::123456789012:user/admin",
            event_time="2024-01-15T10:30:00Z",
        )

        assert "TAG COMPLIANCE VIOLATION" in message
        assert "ec2:instance" in message
        assert "i-1234567890abcdef0" in message
        assert "MISSING REQUIRED TAGS" in message
        assert "site" in message
        assert "cost-center" in message
        assert "REMEDIATION" in message

    def test_build_message_with_invalid_values(self):
        """Test message building with invalid tag values."""
        message = _build_notification_message(
            resource_type="s3:bucket",
            resource_ids=["my-bucket"],
            region="us-west-2",
            account_id="123456789012",
            missing_tags=[],
            invalid_values=[
                {
                    "tagKey": "environment",
                    "currentValue": "invalid",
                    "allowedValues": ["dev", "staging", "prod"],
                }
            ],
            creator="admin",
            event_time="2024-01-15T10:30:00Z",
        )

        assert "INVALID TAG VALUES" in message
        assert "environment" in message
        assert "invalid" in message
        assert "dev, staging, prod" in message

    def test_build_message_with_both_issues(self):
        """Test message building with both missing tags and invalid values."""
        message = _build_notification_message(
            resource_type="rds:db",
            resource_ids=["my-db"],
            region="eu-west-1",
            account_id="123456789012",
            missing_tags=["owner"],
            invalid_values=[
                {"tagKey": "env", "currentValue": "test", "allowedValues": ["dev", "prod"]}
            ],
            creator="dba-user",
            event_time="2024-01-15T10:30:00Z",
        )

        assert "MISSING REQUIRED TAGS" in message
        assert "INVALID TAG VALUES" in message
        assert "owner" in message
        assert "env" in message

    def test_build_message_includes_console_link(self):
        """Test that message includes AWS Console link."""
        message = _build_notification_message(
            resource_type="ec2:instance",
            resource_ids=["i-123"],
            region="us-east-1",
            account_id="123456789012",
            missing_tags=["site"],
            invalid_values=[],
            creator="user",
            event_time="2024-01-15T10:30:00Z",
        )

        assert "console.aws.amazon.com" in message
        assert "us-east-1" in message


class TestBuildSmsMessage:
    """Tests for _build_sms_message function."""

    def test_build_sms_with_missing_tags(self):
        """Test SMS message with missing tags."""
        msg = _build_sms_message(
            resource_type="ec2:instance",
            resource_ids=["i-1234567890abcdef0"],
            missing_tags=["site", "cost-center"],
            invalid_values=[],
        )

        assert "Tag violation" in msg
        assert "ec2:instance" in msg
        assert "missing" in msg
        assert len(msg) <= 160  # SMS length limit

    def test_build_sms_with_invalid_values(self):
        """Test SMS message with invalid values."""
        msg = _build_sms_message(
            resource_type="s3:bucket",
            resource_ids=["my-bucket"],
            missing_tags=[],
            invalid_values=[{"tagKey": "environment"}],
        )

        assert "invalid" in msg
        assert len(msg) <= 160

    def test_build_sms_truncates_long_message(self):
        """Test that SMS message is truncated if too long."""
        msg = _build_sms_message(
            resource_type="ec2:instance",
            resource_ids=["i-very-long-instance-id-that-is-really-long"],
            missing_tags=["very-long-tag-name-1", "very-long-tag-name-2", "very-long-tag-name-3"],
            invalid_values=[],
        )

        assert len(msg) <= 160
        if len(msg) == 160:
            assert msg.endswith("...")


class TestSendSnsNotification:
    """Tests for send_sns_notification function."""

    @patch("tools.sns_notifier.boto3")
    def test_send_notification_success(self, mock_boto3):
        """Test successful notification sending."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"

        mock_sns = MagicMock()
        mock_boto3.client.return_value = mock_sns
        mock_sns.publish.return_value = {"MessageId": "msg-12345"}

        result = send_sns_notification(
            resource_type="ec2:instance",
            resource_ids=["i-123"],
            region="us-east-1",
            account_id="123456789012",
            missing_tags=["site"],
            invalid_values=[],
            creator="admin",
            event_time="2024-01-15T10:30:00Z",
        )

        assert result["success"] is True
        assert result["message_id"] == "msg-12345"
        mock_sns.publish.assert_called_once()

    @patch("tools.sns_notifier.boto3")
    def test_send_notification_with_structured_message(self, mock_boto3):
        """Test that notification uses structured message for different protocols."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"

        mock_sns = MagicMock()
        mock_boto3.client.return_value = mock_sns
        mock_sns.publish.return_value = {"MessageId": "msg-12345"}

        send_sns_notification(
            resource_type="ec2:instance",
            resource_ids=["i-123"],
            region="us-east-1",
            account_id="123456789012",
            missing_tags=["site"],
            invalid_values=[],
        )

        # Verify message structure
        call_kwargs = mock_sns.publish.call_args[1]
        assert call_kwargs["MessageStructure"] == "json"

        message = json.loads(call_kwargs["Message"])
        assert "default" in message
        assert "email" in message
        assert "sms" in message

    def test_send_notification_missing_topic_arn(self):
        """Test error when SNS_TOPIC_ARN is not set."""
        # Remove the env var if it exists
        if "SNS_TOPIC_ARN" in os.environ:
            del os.environ["SNS_TOPIC_ARN"]

        result = send_sns_notification(
            resource_type="ec2:instance",
            resource_ids=["i-123"],
            region="us-east-1",
            account_id="123456789012",
            missing_tags=["site"],
            invalid_values=[],
        )

        assert result["success"] is False
        assert "SNS_TOPIC_ARN" in result["error"]

    @patch("tools.sns_notifier.boto3")
    def test_send_notification_sns_error(self, mock_boto3):
        """Test error handling when SNS publish fails."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"

        mock_sns = MagicMock()
        mock_boto3.client.return_value = mock_sns
        mock_sns.publish.side_effect = Exception("SNS error")

        result = send_sns_notification(
            resource_type="ec2:instance",
            resource_ids=["i-123"],
            region="us-east-1",
            account_id="123456789012",
            missing_tags=["site"],
            invalid_values=[],
        )

        assert result["success"] is False
        assert "SNS error" in result["error"]

    @patch("tools.sns_notifier.boto3")
    def test_send_notification_subject_truncation(self, mock_boto3):
        """Test that subject is truncated to 100 chars."""
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"

        mock_sns = MagicMock()
        mock_boto3.client.return_value = mock_sns
        mock_sns.publish.return_value = {"MessageId": "msg-12345"}

        send_sns_notification(
            resource_type="very:long:resource:type:name:that:exceeds:normal:length",
            resource_ids=["i-123"],
            region="us-east-1",
            account_id="123456789012",
            missing_tags=["site"],
            invalid_values=[],
        )

        call_kwargs = mock_sns.publish.call_args[1]
        assert len(call_kwargs["Subject"]) <= 100

    @patch("tools.sns_notifier.boto3")
    def test_send_notification_uses_correct_topic(self, mock_boto3):
        """Test that notification is sent to correct topic ARN."""
        topic_arn = "arn:aws:sns:us-west-2:999999999999:my-topic"
        os.environ["SNS_TOPIC_ARN"] = topic_arn

        mock_sns = MagicMock()
        mock_boto3.client.return_value = mock_sns
        mock_sns.publish.return_value = {"MessageId": "msg-12345"}

        send_sns_notification(
            resource_type="ec2:instance",
            resource_ids=["i-123"],
            region="us-west-2",
            account_id="999999999999",
            missing_tags=["site"],
            invalid_values=[],
        )

        call_kwargs = mock_sns.publish.call_args[1]
        assert call_kwargs["TopicArn"] == topic_arn
