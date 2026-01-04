"""Unit tests for the dynamodb_rules tool module."""

import pytest
from unittest.mock import patch, MagicMock

from tools.dynamodb_rules import get_tag_rules


class TestGetTagRules:
    """Tests for get_tag_rules function."""

    @patch("tools.dynamodb_rules.boto3")
    def test_get_all_rules(self, mock_boto3):
        """Test fetching all enabled rules."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {
            "Items": [
                {
                    "ruleId": "rule-001",
                    "tagKey": "site",
                    "allowedValues": ["us", "en"],
                    "enabled": True,
                },
                {
                    "ruleId": "rule-002",
                    "tagKey": "environment",
                    "allowedValues": ["dev", "prod"],
                    "enabled": True,
                },
            ]
        }

        result = get_tag_rules()

        assert result["count"] == 2
        assert len(result["rules"]) == 2
        assert result["rules"][0]["tagKey"] == "site"
        assert result["rules"][1]["tagKey"] == "environment"

    @patch("tools.dynamodb_rules.boto3")
    def test_get_rules_by_resource_type(self, mock_boto3):
        """Test filtering rules by resource type."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {
            "Items": [
                {
                    "ruleId": "rule-001",
                    "tagKey": "site",
                    "allowedValues": ["us"],
                    "enabled": True,
                    "resourceTypes": ["ec2:instance", "s3:bucket"],
                },
                {
                    "ruleId": "rule-002",
                    "tagKey": "environment",
                    "allowedValues": ["dev"],
                    "enabled": True,
                    "resourceTypes": ["ec2:instance"],
                },
                {
                    "ruleId": "rule-003",
                    "tagKey": "cost-center",
                    "allowedValues": [],
                    "enabled": True,
                    # No resourceTypes = applies to all
                },
            ]
        }

        result = get_tag_rules("s3:bucket")

        # Should return rules for s3:bucket and rules without resourceTypes
        assert result["count"] == 2
        rule_ids = [r["ruleId"] for r in result["rules"]]
        assert "rule-001" in rule_ids  # Has s3:bucket
        assert "rule-003" in rule_ids  # Applies to all
        assert "rule-002" not in rule_ids  # Only ec2:instance

    @patch("tools.dynamodb_rules.boto3")
    def test_get_rules_empty_table(self, mock_boto3):
        """Test with empty DynamoDB table."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": []}

        result = get_tag_rules()

        assert result["count"] == 0
        assert result["rules"] == []

    @patch("tools.dynamodb_rules.boto3")
    def test_get_rules_with_description(self, mock_boto3):
        """Test that rule descriptions are included."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {
            "Items": [
                {
                    "ruleId": "rule-001",
                    "tagKey": "site",
                    "allowedValues": ["us", "en"],
                    "enabled": True,
                    "description": "Site identifier for cost allocation",
                },
            ]
        }

        result = get_tag_rules()

        assert result["count"] == 1
        assert result["rules"][0]["description"] == "Site identifier for cost allocation"

    @patch("tools.dynamodb_rules.boto3")
    def test_get_rules_error_handling(self, mock_boto3):
        """Test error handling when DynamoDB fails."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.side_effect = Exception("DynamoDB error")

        result = get_tag_rules()

        assert result["count"] == 0
        assert result["rules"] == []
        assert "error" in result
        assert "DynamoDB error" in result["error"]

    @patch("tools.dynamodb_rules.boto3")
    def test_get_rules_uses_correct_table(self, mock_boto3):
        """Test that the correct table name is used."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": []}

        get_tag_rules()

        mock_dynamodb.Table.assert_called_once_with("TagComplianceRules")

    @patch("tools.dynamodb_rules.boto3")
    def test_get_rules_filter_expression(self, mock_boto3):
        """Test that only enabled rules are fetched."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {"Items": []}

        get_tag_rules()

        # Verify the scan uses the enabled filter
        call_kwargs = mock_table.scan.call_args[1]
        assert "FilterExpression" in call_kwargs
        assert "enabled = :enabled" in call_kwargs["FilterExpression"]
        assert call_kwargs["ExpressionAttributeValues"][":enabled"] is True

    @patch("tools.dynamodb_rules.boto3")
    def test_get_rules_no_resource_types_match_all(self, mock_boto3):
        """Test that rules without resourceTypes match all resource types."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {
            "Items": [
                {
                    "ruleId": "rule-universal",
                    "tagKey": "owner",
                    "allowedValues": [],
                    "enabled": True,
                    # No resourceTypes field
                },
            ]
        }

        # Should match any resource type
        result_ec2 = get_tag_rules("ec2:instance")
        assert result_ec2["count"] == 1

        result_s3 = get_tag_rules("s3:bucket")
        assert result_s3["count"] == 1

        result_rds = get_tag_rules("rds:db")
        assert result_rds["count"] == 1

    @patch("tools.dynamodb_rules.boto3")
    def test_get_rules_formats_output_correctly(self, mock_boto3):
        """Test that output is formatted correctly."""
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_boto3.resource.return_value = mock_dynamodb
        mock_dynamodb.Table.return_value = mock_table
        mock_table.scan.return_value = {
            "Items": [
                {
                    "ruleId": "rule-001",
                    "tagKey": "env",
                    "allowedValues": ["dev", "prod"],
                    "enabled": True,
                    "resourceTypes": ["ec2:instance"],
                    "description": "Environment tag",
                    "extraField": "should be ignored",  # Extra fields should not appear
                },
            ]
        }

        result = get_tag_rules()

        rule = result["rules"][0]
        assert set(rule.keys()) == {"ruleId", "tagKey", "allowedValues", "enabled", "resourceTypes", "description"}
        assert rule["ruleId"] == "rule-001"
        assert rule["tagKey"] == "env"
        assert rule["allowedValues"] == ["dev", "prod"]
        assert rule["enabled"] is True
        assert rule["resourceTypes"] == ["ec2:instance"]
        assert rule["description"] == "Environment tag"
