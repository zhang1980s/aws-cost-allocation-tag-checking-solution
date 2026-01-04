"""
Strands Agent definition for tag compliance checking.

This module defines the AI agent that orchestrates tag compliance validation
using Amazon Bedrock for intelligent reasoning.
"""

import logging
import os

from strands import Agent
from strands.models.bedrock import BedrockModel

from tools.dynamodb_rules import get_tag_rules
from tools.tag_checker import check_resource_tags, get_resource_tags
from tools.lark_notifier import send_lark_notification

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an AWS Tag Compliance Agent. Your role is to verify that newly created AWS resources comply with organizational tagging policies.

When analyzing tag compliance, follow these steps:

1. First, retrieve the tag compliance rules from DynamoDB using the get_tag_rules tool.

2. Get the current tags for the resource using the get_resource_tags tool if the tags were not provided in the event.

3. Use the check_resource_tags tool to validate the resource's tags against the rules.

4. If the resource is NOT compliant, use the send_lark_notification tool to alert the team with:
   - Resource type and ID
   - Missing required tags
   - Invalid tag values
   - Remediation guidance

5. Return a summary of the compliance check including:
   - Whether the resource is compliant
   - Which rules passed and which failed
   - Any notifications sent

Be concise and focus on actionable information. Do not be overly verbose."""


class TagComplianceAgent:
    """Agent for checking AWS resource tag compliance."""

    def __init__(self):
        """Initialize the tag compliance agent."""
        self.model_id = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-2-lite-v1:0")
        self.region = os.environ.get("AWS_REGION", "us-east-1")

        logger.info(f"Initializing TagComplianceAgent with model: {self.model_id}")

        # Initialize Bedrock model
        self.model = BedrockModel(
            model_id=self.model_id,
            region_name=self.region,
        )

        # Define available tools
        self.tools = [
            get_tag_rules,
            get_resource_tags,
            check_resource_tags,
            send_lark_notification,
        ]

        # Initialize agent
        self.agent = Agent(
            model=self.model,
            tools=self.tools,
            system_prompt=SYSTEM_PROMPT,
        )

    def check_compliance(self, resource_info: dict) -> dict:
        """
        Check tag compliance for a resource.

        Args:
            resource_info: Dictionary containing resource details:
                - resource_type: Type of AWS resource
                - resource_ids: List of resource IDs
                - tags: Current tags on the resource (if available)
                - region: AWS region
                - account_id: AWS account ID
                - event_name: CloudTrail event name
                - user_identity: User/role that created the resource

        Returns:
            Dictionary with compliance check results
        """
        logger.info(f"Checking compliance for: {resource_info}")

        # Format the prompt for the agent
        prompt = self._format_compliance_prompt(resource_info)

        try:
            # Run the agent
            result = self.agent(prompt)

            # Extract the response
            response_text = str(result)

            return {
                "status": "completed",
                "resource_type": resource_info.get("resource_type"),
                "resource_ids": resource_info.get("resource_ids"),
                "analysis": response_text,
            }

        except Exception as e:
            logger.error(f"Error during compliance check: {e}", exc_info=True)
            return {
                "status": "error",
                "resource_type": resource_info.get("resource_type"),
                "resource_ids": resource_info.get("resource_ids"),
                "error": str(e),
            }

    def _format_compliance_prompt(self, resource_info: dict) -> str:
        """Format the compliance check prompt for the agent."""
        tags_info = resource_info.get("tags", [])
        tags_str = ", ".join([f"{t['Key']}={t['Value']}" for t in tags_info]) if tags_info else "No tags provided"

        user_identity = resource_info.get("user_identity", {})
        creator = user_identity.get("arn", user_identity.get("userName", "Unknown"))

        prompt = f"""A new AWS resource was created and needs tag compliance verification.

Resource Details:
- Type: {resource_info.get('resource_type')}
- Resource IDs: {', '.join(resource_info.get('resource_ids', []))}
- Region: {resource_info.get('region')}
- Account ID: {resource_info.get('account_id')}
- Created by: {creator}
- Event Time: {resource_info.get('event_time', 'Unknown')}
- Current Tags: {tags_str}

Please check this resource for tag compliance:
1. Get the compliance rules
2. Get the resource's current tags (if needed)
3. Check compliance against rules
4. If non-compliant, send notification with details
5. Provide a summary of the results"""

        return prompt
