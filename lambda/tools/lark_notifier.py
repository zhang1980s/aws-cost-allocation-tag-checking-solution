"""
Lark/Feishu notification tool for sending tag compliance alerts.

This tool sends notifications to Lark/Feishu when resources are non-compliant.
"""

import json
import logging
import os
import time
from typing import Optional

import boto3
import requests
from strands import tool

logger = logging.getLogger(__name__)

# Cache for access token
_token_cache = {
    "token": None,
    "expires_at": 0,
}


def _get_lark_credentials() -> dict:
    """Fetch Lark credentials from Secrets Manager."""
    secret_name = os.environ.get("LARK_SECRET_NAME", "tag-compliance/lark-credentials")
    region = os.environ.get("AWS_REGION", "us-east-1")

    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


def _get_access_token(app_id: str, app_secret: str) -> str:
    """Get Lark access token, using cache if valid."""
    current_time = time.time()

    # Check if cached token is still valid (with 5 minute buffer)
    if _token_cache["token"] and _token_cache["expires_at"] > current_time + 300:
        return _token_cache["token"]

    # Get new token
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    response = requests.post(
        url,
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != 0:
        raise Exception(f"Failed to get Lark access token: {data.get('msg')}")

    token = data["tenant_access_token"]
    # Token is valid for 2 hours (7200 seconds)
    _token_cache["token"] = token
    _token_cache["expires_at"] = current_time + 7200

    return token


def _send_message(token: str, chat_id: str, content: dict) -> dict:
    """Send a message to Lark chat."""
    url = "https://open.larksuite.com/open-apis/im/v1/messages"
    params = {"receive_id_type": "chat_id"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(content),
    }

    response = requests.post(url, params=params, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


@tool
def send_lark_notification(
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
    Send a tag compliance violation notification to Lark/Feishu.

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
        - message_id: ID of the sent message (if successful)
        - error: Error message (if failed)
    """
    logger.info(f"Sending Lark notification for {resource_type}: {resource_ids}")

    try:
        # Get credentials
        credentials = _get_lark_credentials()
        app_id = credentials["appId"]
        app_secret = credentials["appSecret"]
        chat_id = credentials["chatId"]

        # Get access token
        token = _get_access_token(app_id, app_secret)

        # Build message card
        card = _build_compliance_card(
            resource_type=resource_type,
            resource_ids=resource_ids,
            region=region,
            account_id=account_id,
            missing_tags=missing_tags,
            invalid_values=invalid_values,
            creator=creator,
            event_time=event_time,
        )

        # Send message
        result = _send_message(token, chat_id, card)

        if result.get("code") == 0:
            message_id = result.get("data", {}).get("message_id")
            logger.info(f"Notification sent successfully: {message_id}")
            return {
                "success": True,
                "message_id": message_id,
            }
        else:
            error = result.get("msg", "Unknown error")
            logger.error(f"Failed to send notification: {error}")
            return {
                "success": False,
                "error": error,
            }

    except Exception as e:
        logger.error(f"Error sending Lark notification: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def _build_compliance_card(
    resource_type: str,
    resource_ids: list,
    region: str,
    account_id: str,
    missing_tags: list,
    invalid_values: list,
    creator: str,
    event_time: str,
) -> dict:
    """Build an interactive card for the compliance violation."""

    # Header
    header = {
        "title": {
            "tag": "plain_text",
            "content": "Tag Compliance Violation",
        },
        "template": "red",
    }

    # Resource info section
    resource_info = f"**Resource Type:** {resource_type}\n"
    resource_info += f"**Resource IDs:** {', '.join(resource_ids)}\n"
    resource_info += f"**Region:** {region}\n"
    resource_info += f"**Account ID:** {account_id}\n"
    resource_info += f"**Created By:** {creator}\n"
    resource_info += f"**Event Time:** {event_time}"

    elements = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": resource_info,
            },
        },
        {"tag": "hr"},
    ]

    # Missing tags section
    if missing_tags:
        missing_content = "**Missing Required Tags:**\n"
        for tag in missing_tags:
            missing_content += f"- `{tag}`\n"
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": missing_content,
            },
        })

    # Invalid values section
    if invalid_values:
        invalid_content = "**Invalid Tag Values:**\n"
        for item in invalid_values:
            tag_key = item.get("tagKey")
            current = item.get("currentValue")
            allowed = item.get("allowedValues", [])
            invalid_content += f"- `{tag_key}`: Current value `{current}`, allowed: {allowed}\n"
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": invalid_content,
            },
        })

    # Remediation section
    elements.append({"tag": "hr"})
    remediation = "**Remediation:**\n"
    remediation += "Please add the missing tags and correct any invalid values to comply with organizational tagging policies.\n\n"
    remediation += f"[View Resource in AWS Console](https://console.aws.amazon.com/resource-groups/home?region={region})"

    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": remediation,
        },
    })

    return {
        "config": {"wide_screen_mode": True},
        "header": header,
        "elements": elements,
    }
