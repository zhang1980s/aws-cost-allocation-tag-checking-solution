"""Unit tests for the Lambda handler module."""

import json
import pytest
from unittest.mock import patch, MagicMock

# Import after setting env vars (done in conftest.py)
from handler import (
    lambda_handler,
    extract_resource_info,
    extract_ec2_tags,
    extract_tags_from_response,
    extract_rds_tags,
    extract_lambda_tags,
    extract_asg_tags,
)


class TestExtractResourceInfo:
    """Tests for extract_resource_info function."""

    def test_extract_ec2_runinstances(self, sample_ec2_event):
        """Test extraction of EC2 RunInstances event."""
        result = extract_resource_info(sample_ec2_event)

        assert result is not None
        assert result["resource_type"] == "ec2:instance"
        assert result["resource_ids"] == ["i-0123456789abcdef0"]
        assert result["region"] == "us-east-1"
        assert result["account_id"] == "123456789012"
        assert result["event_name"] == "RunInstances"
        assert len(result["tags"]) == 2
        assert result["tags"][0]["Key"] == "Name"

    def test_extract_s3_createbucket(self, sample_s3_event):
        """Test extraction of S3 CreateBucket event."""
        result = extract_resource_info(sample_s3_event)

        assert result is not None
        assert result["resource_type"] == "s3:bucket"
        assert result["resource_ids"] == ["my-test-bucket-123"]
        assert result["region"] == "us-east-1"
        assert result["tags"] == []

    def test_extract_rds_createdbinstance(self, sample_rds_event):
        """Test extraction of RDS CreateDBInstance event."""
        result = extract_resource_info(sample_rds_event)

        assert result is not None
        assert result["resource_type"] == "rds:db"
        assert result["resource_ids"] == ["my-test-db"]
        assert result["resource_arn"] == "arn:aws:rds:us-east-1:123456789012:db:my-test-db"
        assert len(result["tags"]) == 2

    def test_extract_unsupported_event(self):
        """Test that unsupported events return None."""
        event = {
            "detail": {
                "eventSource": "unknown.amazonaws.com",
                "eventName": "UnknownAction",
            }
        }
        result = extract_resource_info(event)
        assert result is None

    def test_extract_empty_event(self):
        """Test handling of empty event."""
        result = extract_resource_info({})
        assert result is None

    def test_extract_ec2_create_volume(self):
        """Test extraction of EC2 CreateVolume event."""
        event = {
            "detail": {
                "eventSource": "ec2.amazonaws.com",
                "eventName": "CreateVolume",
                "awsRegion": "us-west-2",
                "recipientAccountId": "123456789012",
                "eventTime": "2024-01-15T10:30:00Z",
                "userIdentity": {"arn": "arn:aws:iam::123456789012:user/admin"},
                "responseElements": {
                    "volumeId": "vol-0123456789abcdef0",
                    "tagSet": {"items": []},
                },
            }
        }
        result = extract_resource_info(event)

        assert result is not None
        assert result["resource_type"] == "ec2:volume"
        assert result["resource_ids"] == ["vol-0123456789abcdef0"]

    def test_extract_ec2_create_vpc(self):
        """Test extraction of EC2 CreateVpc event."""
        event = {
            "detail": {
                "eventSource": "ec2.amazonaws.com",
                "eventName": "CreateVpc",
                "awsRegion": "us-east-1",
                "recipientAccountId": "123456789012",
                "eventTime": "2024-01-15T10:30:00Z",
                "userIdentity": {},
                "responseElements": {
                    "vpc": {
                        "vpcId": "vpc-0123456789abcdef0",
                        "tagSet": {"items": []},
                    }
                },
            }
        }
        result = extract_resource_info(event)

        assert result is not None
        assert result["resource_type"] == "ec2:vpc"
        assert result["resource_ids"] == ["vpc-0123456789abcdef0"]

    def test_extract_lambda_createfunction(self):
        """Test extraction of Lambda CreateFunction event."""
        event = {
            "detail": {
                "eventSource": "lambda.amazonaws.com",
                "eventName": "CreateFunction20150331",
                "awsRegion": "us-east-1",
                "recipientAccountId": "123456789012",
                "eventTime": "2024-01-15T10:30:00Z",
                "userIdentity": {},
                "responseElements": {
                    "functionName": "my-function",
                    "functionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
                    "tags": {"environment": "dev"},
                },
            }
        }
        result = extract_resource_info(event)

        assert result is not None
        assert result["resource_type"] == "lambda:function"
        assert result["resource_ids"] == ["my-function"]
        assert len(result["tags"]) == 1


class TestExtractTags:
    """Tests for tag extraction helper functions."""

    def test_extract_ec2_tags(self):
        """Test EC2 tag extraction."""
        instance = {
            "tagSet": {
                "items": [
                    {"key": "Name", "value": "test"},
                    {"key": "env", "value": "dev"},
                ]
            }
        }
        tags = extract_ec2_tags(instance)

        assert len(tags) == 2
        assert tags[0] == {"Key": "Name", "Value": "test"}
        assert tags[1] == {"Key": "env", "Value": "dev"}

    def test_extract_ec2_tags_empty(self):
        """Test EC2 tag extraction with no tags."""
        instance = {}
        tags = extract_ec2_tags(instance)
        assert tags == []

    def test_extract_tags_from_response(self):
        """Test generic tag extraction from response."""
        response = {
            "tagSet": {
                "items": [{"key": "project", "value": "compliance"}]
            }
        }
        tags = extract_tags_from_response(response)

        assert len(tags) == 1
        assert tags[0] == {"Key": "project", "Value": "compliance"}

    def test_extract_rds_tags(self):
        """Test RDS tag extraction."""
        db_resource = {
            "tagList": [
                {"key": "environment", "value": "prod"},
                {"key": "team", "value": "platform"},
            ]
        }
        tags = extract_rds_tags(db_resource)

        assert len(tags) == 2
        assert tags[0] == {"Key": "environment", "Value": "prod"}

    def test_extract_lambda_tags(self):
        """Test Lambda tag extraction."""
        response = {
            "tags": {
                "environment": "dev",
                "cost-center": "engineering",
            }
        }
        tags = extract_lambda_tags(response)

        assert len(tags) == 2
        assert {"Key": "environment", "Value": "dev"} in tags
        assert {"Key": "cost-center", "Value": "engineering"} in tags

    def test_extract_asg_tags(self):
        """Test Auto Scaling Group tag extraction."""
        params = {
            "tags": [
                {"key": "environment", "value": "staging"},
                {"key": "Name", "value": "my-asg"},
            ]
        }
        tags = extract_asg_tags(params)

        assert len(tags) == 2
        assert tags[0] == {"Key": "environment", "Value": "staging"}


class TestLambdaHandler:
    """Tests for the main lambda_handler function."""

    def test_handler_test_event(self):
        """Test handler with test event."""
        event = {"test": True}
        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Test successful"

    def test_handler_empty_event(self):
        """Test handler with empty event (no actionable resource)."""
        event = {}
        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "not applicable" in body["message"].lower()

    @patch("handler.TagComplianceAgent")
    def test_handler_ec2_event(self, mock_agent_class, sample_ec2_event):
        """Test handler with EC2 event."""
        # Mock the agent
        mock_agent = MagicMock()
        mock_agent.check_compliance.return_value = {
            "status": "completed",
            "compliant": True,
        }
        mock_agent_class.return_value = mock_agent

        result = lambda_handler(sample_ec2_event, None)

        assert result["statusCode"] == 200
        mock_agent.check_compliance.assert_called_once()

        # Verify resource info was passed correctly
        call_args = mock_agent.check_compliance.call_args[0][0]
        assert call_args["resource_type"] == "ec2:instance"
        assert call_args["resource_ids"] == ["i-0123456789abcdef0"]

    @patch("handler.TagComplianceAgent")
    def test_handler_agent_error(self, mock_agent_class, sample_ec2_event):
        """Test handler when agent raises an error."""
        mock_agent = MagicMock()
        mock_agent.check_compliance.side_effect = Exception("Bedrock error")
        mock_agent_class.return_value = mock_agent

        result = lambda_handler(sample_ec2_event, None)

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "error" in body
        assert "Bedrock error" in body["error"]

    def test_handler_skip_check_event(self):
        """Test handler skips events marked for skipping."""
        event = {
            "detail": {
                "eventSource": "s3.amazonaws.com",
                "eventName": "PutBucketTagging",
                "awsRegion": "us-east-1",
                "recipientAccountId": "123456789012",
                "eventTime": "2024-01-15T10:30:00Z",
                "userIdentity": {},
                "requestParameters": {"bucketName": "my-bucket"},
            }
        }
        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "skipped" in body["message"].lower()
