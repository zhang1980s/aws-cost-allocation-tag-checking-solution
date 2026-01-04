"""
Tag checker tool for validating resource tags against compliance rules.

This tool checks AWS resource tags and validates them against defined rules.
"""

import logging
import os

import boto3
from strands import tool

logger = logging.getLogger(__name__)


@tool
def get_resource_tags(resource_type: str, resource_id: str, region: str = None) -> dict:
    """
    Get the current tags for an AWS resource.

    Args:
        resource_type: Type of AWS resource (e.g., "ec2:instance", "s3:bucket", "rds:db")
        resource_id: The resource ID or ARN
        region: AWS region (optional, defaults to environment variable)

    Returns:
        Dictionary containing:
        - tags: List of tags with Key and Value
        - resource_type: The resource type
        - resource_id: The resource ID
    """
    if region is None:
        region = os.environ.get("AWS_REGION", "us-east-1")

    logger.info(f"Getting tags for {resource_type}: {resource_id} in {region}")

    try:
        tags = []

        if resource_type.startswith("ec2:"):
            ec2 = boto3.client("ec2", region_name=region)

            if resource_type == "ec2:instance":
                response = ec2.describe_instances(InstanceIds=[resource_id])
                for reservation in response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        tags = instance.get("Tags", [])
            elif resource_type == "ec2:volume":
                response = ec2.describe_volumes(VolumeIds=[resource_id])
                for volume in response.get("Volumes", []):
                    tags = volume.get("Tags", [])
            elif resource_type in ["ec2:vpc", "ec2:subnet", "ec2:security-group", "ec2:eip"]:
                response = ec2.describe_tags(
                    Filters=[{"Name": "resource-id", "Values": [resource_id]}]
                )
                tags = [{"Key": t["Key"], "Value": t["Value"]} for t in response.get("Tags", [])]

        elif resource_type == "s3:bucket":
            s3 = boto3.client("s3", region_name=region)
            try:
                response = s3.get_bucket_tagging(Bucket=resource_id)
                tags = response.get("TagSet", [])
            except s3.exceptions.ClientError as e:
                if e.response.get("Error", {}).get("Code") == "NoSuchTagSet":
                    tags = []
                else:
                    raise

        elif resource_type.startswith("rds:"):
            rds = boto3.client("rds", region_name=region)
            # For RDS, resource_id might be the ARN or identifier
            if not resource_id.startswith("arn:"):
                # Build ARN from identifier
                sts = boto3.client("sts")
                account_id = sts.get_caller_identity()["Account"]
                if resource_type == "rds:db":
                    resource_id = f"arn:aws:rds:{region}:{account_id}:db:{resource_id}"
                elif resource_type == "rds:cluster":
                    resource_id = f"arn:aws:rds:{region}:{account_id}:cluster:{resource_id}"

            response = rds.list_tags_for_resource(ResourceName=resource_id)
            tags = response.get("TagList", [])

        elif resource_type == "lambda:function":
            lambda_client = boto3.client("lambda", region_name=region)
            response = lambda_client.list_tags(Resource=resource_id)
            tags = [{"Key": k, "Value": v} for k, v in response.get("Tags", {}).items()]

        elif resource_type == "elb:loadbalancer":
            elbv2 = boto3.client("elbv2", region_name=region)
            response = elbv2.describe_tags(ResourceArns=[resource_id])
            for desc in response.get("TagDescriptions", []):
                tags = desc.get("Tags", [])

        elif resource_type == "autoscaling:group":
            autoscaling = boto3.client("autoscaling", region_name=region)
            response = autoscaling.describe_tags(
                Filters=[
                    {"Name": "auto-scaling-group", "Values": [resource_id]},
                ]
            )
            tags = [{"Key": t["Key"], "Value": t["Value"]} for t in response.get("Tags", [])]

        logger.info(f"Found {len(tags)} tags for {resource_type}:{resource_id}")

        return {
            "tags": tags,
            "resource_type": resource_type,
            "resource_id": resource_id,
        }

    except Exception as e:
        logger.error(f"Error getting resource tags: {e}", exc_info=True)
        return {
            "tags": [],
            "resource_type": resource_type,
            "resource_id": resource_id,
            "error": str(e),
        }


@tool
def check_resource_tags(tags: list, rules: list) -> dict:
    """
    Check resource tags against compliance rules.

    Args:
        tags: List of tags on the resource, each with Key and Value
        rules: List of compliance rules, each with:
            - tagKey: Required tag key
            - allowedValues: List of allowed values (empty = any value allowed)

    Returns:
        Dictionary containing:
        - compliant: Boolean indicating overall compliance
        - passed_rules: List of rules that passed
        - failed_rules: List of rules that failed with details
        - missing_tags: List of required tags that are missing
        - invalid_values: List of tags with invalid values
    """
    logger.info(f"Checking {len(tags)} tags against {len(rules)} rules")

    # Create a dict of current tags for easy lookup
    tag_dict = {tag.get("Key"): tag.get("Value") for tag in tags}

    passed_rules = []
    failed_rules = []
    missing_tags = []
    invalid_values = []

    for rule in rules:
        tag_key = rule.get("tagKey")
        allowed_values = rule.get("allowedValues", [])
        rule_id = rule.get("ruleId", tag_key)

        if tag_key not in tag_dict:
            # Tag is missing
            missing_tags.append(tag_key)
            failed_rules.append({
                "ruleId": rule_id,
                "tagKey": tag_key,
                "reason": "missing",
                "message": f"Required tag '{tag_key}' is missing",
            })
        else:
            tag_value = tag_dict[tag_key]
            # Check if value is allowed (empty list means any value is OK)
            if allowed_values and tag_value not in allowed_values:
                invalid_values.append({
                    "tagKey": tag_key,
                    "currentValue": tag_value,
                    "allowedValues": allowed_values,
                })
                failed_rules.append({
                    "ruleId": rule_id,
                    "tagKey": tag_key,
                    "reason": "invalid_value",
                    "message": f"Tag '{tag_key}' has invalid value '{tag_value}'. Allowed: {allowed_values}",
                })
            else:
                passed_rules.append({
                    "ruleId": rule_id,
                    "tagKey": tag_key,
                    "value": tag_value,
                })

    compliant = len(failed_rules) == 0

    result = {
        "compliant": compliant,
        "total_rules": len(rules),
        "passed_count": len(passed_rules),
        "failed_count": len(failed_rules),
        "passed_rules": passed_rules,
        "failed_rules": failed_rules,
        "missing_tags": missing_tags,
        "invalid_values": invalid_values,
    }

    logger.info(f"Compliance check result: compliant={compliant}, passed={len(passed_rules)}, failed={len(failed_rules)}")

    return result
