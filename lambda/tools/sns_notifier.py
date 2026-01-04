"""
Amazon SNS notification tool for sending tag compliance alerts.

This tool publishes notifications to an SNS topic when resources are non-compliant.
SNS supports multiple subscription types: Email, SMS, HTTP/HTTPS webhooks, Lambda,
SQS, and mobile push notifications.
"""

import json
import logging
import os

import boto3
from strands import tool

logger = logging.getLogger(__name__)


@tool
def send_sns_notification(
    resource_type: str,
    resource_ids: list,
    region: str,
    account_id: str,
    missing_tags: list,
    invalid_values: list,
    creator: str = "Unknown",
    event_time: str = "Unknown",
) -> dict:
    """
    Send a tag compliance violation notification to Amazon SNS.

    Args:
        resource_type: Type of AWS resource (e.g., "ec2:instance", "s3:bucket")
        resource_ids: List of resource IDs that are non-compliant
        region: AWS region where the resource was created
        account_id: AWS account ID
        missing_tags: List of required tags that are missing
        invalid_values: List of tags with invalid values, each with:
            - tagKey: The tag key
            - currentValue: Current value on the resource
            - allowedValues: List of allowed values
        creator: ARN or name of who created the resource
        event_time: When the resource was created

    Returns:
        Dictionary containing:
        - success: Boolean indicating if notification was sent
        - message_id: SNS message ID (if successful)
        - error: Error message (if failed)
    """
    topic_arn = os.environ.get("SNS_TOPIC_ARN")
    if not topic_arn:
        logger.error("SNS_TOPIC_ARN environment variable not set")
        return {
            "success": False,
            "error": "SNS_TOPIC_ARN environment variable not set",
        }

    logger.info(f"Sending SNS notification for {resource_type}: {resource_ids}")

    try:
        sns_client = boto3.client("sns", region_name=os.environ.get("AWS_REGION", "us-east-1"))

        # Build the notification message
        subject = f"Tag Compliance Violation: {resource_type}"
        message = _build_notification_message(
            resource_type=resource_type,
            resource_ids=resource_ids,
            region=region,
            account_id=account_id,
            missing_tags=missing_tags,
            invalid_values=invalid_values,
            creator=creator,
            event_time=event_time,
        )

        # Build structured message for different protocols
        message_structure = {
            "default": message,
            "email": message,
            "sms": _build_sms_message(resource_type, resource_ids, missing_tags, invalid_values),
        }

        # Publish to SNS
        response = sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject[:100],  # SNS subject max 100 chars
            Message=json.dumps(message_structure),
            MessageStructure="json",
        )

        message_id = response.get("MessageId")
        logger.info(f"SNS notification sent successfully: {message_id}")

        return {
            "success": True,
            "message_id": message_id,
        }

    except Exception as e:
        logger.error(f"Error sending SNS notification: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def _build_notification_message(
    resource_type: str,
    resource_ids: list,
    region: str,
    account_id: str,
    missing_tags: list,
    invalid_values: list,
    creator: str,
    event_time: str,
) -> str:
    """Build a detailed notification message for email and other protocols."""
    lines = [
        "=" * 60,
        "TAG COMPLIANCE VIOLATION DETECTED",
        "=" * 60,
        "",
        "RESOURCE DETAILS",
        "-" * 40,
        f"Resource Type: {resource_type}",
        f"Resource IDs: {', '.join(resource_ids)}",
        f"Region: {region}",
        f"Account ID: {account_id}",
        f"Created By: {creator}",
        f"Event Time: {event_time}",
        "",
    ]

    if missing_tags:
        lines.extend([
            "MISSING REQUIRED TAGS",
            "-" * 40,
        ])
        for tag in missing_tags:
            lines.append(f"  - {tag}")
        lines.append("")

    if invalid_values:
        lines.extend([
            "INVALID TAG VALUES",
            "-" * 40,
        ])
        for item in invalid_values:
            tag_key = item.get("tagKey")
            current = item.get("currentValue")
            allowed = item.get("allowedValues", [])
            lines.append(f"  - {tag_key}")
            lines.append(f"    Current value: {current}")
            lines.append(f"    Allowed values: {', '.join(allowed)}")
        lines.append("")

    lines.extend([
        "REMEDIATION",
        "-" * 40,
        "Please add the missing tags and correct any invalid values",
        "to comply with organizational tagging policies.",
        "",
        f"AWS Console: https://{region}.console.aws.amazon.com/resource-groups/home?region={region}",
        "",
        "=" * 60,
    ])

    return "\n".join(lines)


def _build_sms_message(
    resource_type: str,
    resource_ids: list,
    missing_tags: list,
    invalid_values: list,
) -> str:
    """Build a short SMS message (max 160 chars recommended)."""
    resource_id = resource_ids[0] if resource_ids else "unknown"
    issues = []

    if missing_tags:
        issues.append(f"missing: {', '.join(missing_tags[:2])}")
    if invalid_values:
        invalid_keys = [v.get("tagKey") for v in invalid_values[:2]]
        issues.append(f"invalid: {', '.join(invalid_keys)}")

    issues_str = "; ".join(issues)
    msg = f"Tag violation: {resource_type} {resource_id[:20]} - {issues_str}"

    # Truncate to 160 chars for SMS
    if len(msg) > 160:
        msg = msg[:157] + "..."

    return msg
