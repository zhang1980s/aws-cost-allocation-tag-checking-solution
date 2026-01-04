"""
DynamoDB rules tool for fetching tag compliance rules.

This tool retrieves tag compliance rules from a DynamoDB table.
Rules define which tags are required and their allowed values.
"""

import logging
import os

import boto3
from strands import tool

logger = logging.getLogger(__name__)


@tool
def get_tag_rules(resource_type: str = None) -> dict:
    """
    Fetch tag compliance rules from DynamoDB.

    Args:
        resource_type: Optional resource type to filter rules (e.g., "ec2:instance", "s3:bucket").
                      If not provided, returns all enabled rules.

    Returns:
        Dictionary containing:
        - rules: List of tag compliance rules, each with:
            - ruleId: Unique rule identifier
            - tagKey: Required tag key
            - allowedValues: List of allowed values (empty = any value allowed)
            - enabled: Whether the rule is active
            - resourceTypes: Optional list of resource types the rule applies to
            - description: Optional rule description
        - count: Number of rules returned
    """
    table_name = os.environ.get("RULES_TABLE_NAME", "TagComplianceRules")
    region = os.environ.get("AWS_REGION", "us-east-1")

    logger.info(f"Fetching tag rules from {table_name} for resource_type={resource_type}")

    try:
        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)

        # Scan for all enabled rules
        response = table.scan(
            FilterExpression="enabled = :enabled",
            ExpressionAttributeValues={":enabled": True},
        )

        rules = response.get("Items", [])

        # Filter by resource type if specified
        if resource_type:
            filtered_rules = []
            for rule in rules:
                rule_resource_types = rule.get("resourceTypes", [])
                # Include rule if no resource types specified (applies to all)
                # or if the resource type matches
                if not rule_resource_types or resource_type in rule_resource_types:
                    filtered_rules.append(rule)
            rules = filtered_rules

        # Format rules for output
        formatted_rules = []
        for rule in rules:
            formatted_rule = {
                "ruleId": rule.get("ruleId"),
                "tagKey": rule.get("tagKey"),
                "allowedValues": rule.get("allowedValues", []),
                "enabled": rule.get("enabled", True),
            }
            if rule.get("resourceTypes"):
                formatted_rule["resourceTypes"] = rule.get("resourceTypes")
            if rule.get("description"):
                formatted_rule["description"] = rule.get("description")
            formatted_rules.append(formatted_rule)

        logger.info(f"Found {len(formatted_rules)} applicable rules")

        return {
            "rules": formatted_rules,
            "count": len(formatted_rules),
        }

    except Exception as e:
        logger.error(f"Error fetching tag rules: {e}", exc_info=True)
        return {
            "rules": [],
            "count": 0,
            "error": str(e),
        }
