"""Pytest fixtures for Tag Compliance Lambda tests."""

import os
import pytest


@pytest.fixture(autouse=True)
def set_env_vars():
    """Set environment variables for all tests."""
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["RULES_TABLE_NAME"] = "TagComplianceRules"
    os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:tag-compliance-notifications"
    os.environ["BEDROCK_MODEL_ID"] = "amazon.nova-2-lite-v1:0"
    os.environ["LOG_LEVEL"] = "DEBUG"
    yield
    # Cleanup is optional since tests run in isolation


@pytest.fixture
def sample_ec2_event():
    """Sample EC2 RunInstances CloudTrail event."""
    return {
        "version": "0",
        "id": "12345678-1234-1234-1234-123456789012",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.ec2",
        "account": "123456789012",
        "time": "2024-01-15T10:30:00Z",
        "region": "us-east-1",
        "detail": {
            "eventVersion": "1.08",
            "eventTime": "2024-01-15T10:30:00Z",
            "eventSource": "ec2.amazonaws.com",
            "eventName": "RunInstances",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "userIdentity": {
                "type": "AssumedRole",
                "arn": "arn:aws:sts::123456789012:assumed-role/Admin/user@example.com",
                "userName": "user@example.com",
            },
            "responseElements": {
                "instancesSet": {
                    "items": [
                        {
                            "instanceId": "i-0123456789abcdef0",
                            "tagSet": {
                                "items": [
                                    {"key": "Name", "value": "test-instance"},
                                    {"key": "environment", "value": "dev"},
                                ]
                            },
                        }
                    ]
                }
            },
            "requestParameters": {
                "instanceType": "t3.micro",
            },
        },
    }


@pytest.fixture
def sample_s3_event():
    """Sample S3 CreateBucket CloudTrail event."""
    return {
        "version": "0",
        "id": "12345678-1234-1234-1234-123456789012",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2024-01-15T10:30:00Z",
        "region": "us-east-1",
        "detail": {
            "eventVersion": "1.08",
            "eventTime": "2024-01-15T10:30:00Z",
            "eventSource": "s3.amazonaws.com",
            "eventName": "CreateBucket",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "userIdentity": {
                "type": "IAMUser",
                "arn": "arn:aws:iam::123456789012:user/admin",
                "userName": "admin",
            },
            "requestParameters": {
                "bucketName": "my-test-bucket-123",
            },
            "responseElements": None,
        },
    }


@pytest.fixture
def sample_rds_event():
    """Sample RDS CreateDBInstance CloudTrail event."""
    return {
        "version": "0",
        "id": "12345678-1234-1234-1234-123456789012",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.rds",
        "account": "123456789012",
        "time": "2024-01-15T10:30:00Z",
        "region": "us-east-1",
        "detail": {
            "eventVersion": "1.08",
            "eventTime": "2024-01-15T10:30:00Z",
            "eventSource": "rds.amazonaws.com",
            "eventName": "CreateDBInstance",
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
            "userIdentity": {
                "type": "IAMUser",
                "arn": "arn:aws:iam::123456789012:user/admin",
            },
            "responseElements": {
                "dBInstance": {
                    "dBInstanceIdentifier": "my-test-db",
                    "dBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:my-test-db",
                    "tagList": [
                        {"key": "environment", "value": "staging"},
                        {"key": "cost-center", "value": "engineering"},
                    ],
                }
            },
        },
    }


@pytest.fixture
def sample_tag_rules():
    """Sample tag compliance rules."""
    return [
        {
            "ruleId": "rule-001",
            "tagKey": "site",
            "allowedValues": ["us", "en"],
            "enabled": True,
        },
        {
            "ruleId": "rule-002",
            "tagKey": "environment",
            "allowedValues": ["dev", "staging", "prod"],
            "enabled": True,
        },
        {
            "ruleId": "rule-003",
            "tagKey": "cost-center",
            "allowedValues": [],  # Any value allowed
            "enabled": True,
        },
    ]


@pytest.fixture
def compliant_tags():
    """Tags that comply with sample rules."""
    return [
        {"Key": "site", "Value": "us"},
        {"Key": "environment", "Value": "dev"},
        {"Key": "cost-center", "Value": "engineering"},
    ]


@pytest.fixture
def non_compliant_tags():
    """Tags that do not comply with sample rules."""
    return [
        {"Key": "Name", "Value": "test-instance"},
        {"Key": "environment", "Value": "invalid-env"},  # Invalid value
        # Missing: site, cost-center
    ]
