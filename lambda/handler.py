"""
AWS Tag Compliance Checker Lambda Handler

This Lambda function is triggered by EventBridge when AWS resources are created.
It uses Strands Agents SDK with Amazon Bedrock to analyze tag compliance.
"""

import json
import logging
import os
from typing import Any

from agent import TagComplianceAgent

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(level=getattr(logging, log_level))
logger = logging.getLogger(__name__)


def extract_resource_info(event: dict) -> dict | None:
    """Extract resource information from CloudTrail event."""
    try:
        detail = event.get("detail", {})
        event_name = detail.get("eventName", "")
        event_source = detail.get("eventSource", "")
        response_elements = detail.get("responseElements", {}) or {}
        request_parameters = detail.get("requestParameters", {}) or {}

        resource_info = {
            "event_name": event_name,
            "event_source": event_source,
            "region": detail.get("awsRegion", ""),
            "account_id": detail.get("recipientAccountId", ""),
            "event_time": detail.get("eventTime", ""),
            "user_identity": detail.get("userIdentity", {}),
        }

        # Extract resource-specific information
        if event_source == "ec2.amazonaws.com":
            if event_name == "RunInstances":
                instances = response_elements.get("instancesSet", {}).get("items", [])
                if instances:
                    resource_info["resource_type"] = "ec2:instance"
                    resource_info["resource_ids"] = [i.get("instanceId") for i in instances]
                    resource_info["tags"] = extract_ec2_tags(instances[0])
            elif event_name == "CreateVolume":
                resource_info["resource_type"] = "ec2:volume"
                resource_info["resource_ids"] = [response_elements.get("volumeId")]
                resource_info["tags"] = extract_tags_from_response(response_elements)
            elif event_name == "AllocateAddress":
                resource_info["resource_type"] = "ec2:eip"
                resource_info["resource_ids"] = [response_elements.get("allocationId")]
                resource_info["tags"] = []
            elif event_name == "CreateVpc":
                resource_info["resource_type"] = "ec2:vpc"
                vpc = response_elements.get("vpc", {})
                resource_info["resource_ids"] = [vpc.get("vpcId")]
                resource_info["tags"] = extract_tags_from_response(vpc)
            elif event_name == "CreateSubnet":
                resource_info["resource_type"] = "ec2:subnet"
                subnet = response_elements.get("subnet", {})
                resource_info["resource_ids"] = [subnet.get("subnetId")]
                resource_info["tags"] = extract_tags_from_response(subnet)
            elif event_name == "CreateSecurityGroup":
                resource_info["resource_type"] = "ec2:security-group"
                resource_info["resource_ids"] = [response_elements.get("groupId")]
                resource_info["tags"] = []

        elif event_source == "s3.amazonaws.com":
            if event_name == "CreateBucket":
                resource_info["resource_type"] = "s3:bucket"
                resource_info["resource_ids"] = [request_parameters.get("bucketName")]
                resource_info["tags"] = []
            elif event_name == "PutBucketTagging":
                resource_info["resource_type"] = "s3:bucket"
                resource_info["resource_ids"] = [request_parameters.get("bucketName")]
                # Tags are in request, but bucket already exists
                resource_info["skip_check"] = True

        elif event_source == "rds.amazonaws.com":
            if event_name == "CreateDBInstance":
                db_instance = response_elements.get("dBInstance", {})
                resource_info["resource_type"] = "rds:db"
                resource_info["resource_ids"] = [db_instance.get("dBInstanceIdentifier")]
                resource_info["resource_arn"] = db_instance.get("dBInstanceArn")
                resource_info["tags"] = extract_rds_tags(db_instance)
            elif event_name == "CreateDBCluster":
                db_cluster = response_elements.get("dBCluster", {})
                resource_info["resource_type"] = "rds:cluster"
                resource_info["resource_ids"] = [db_cluster.get("dBClusterIdentifier")]
                resource_info["resource_arn"] = db_cluster.get("dBClusterArn")
                resource_info["tags"] = extract_rds_tags(db_cluster)

        elif event_source == "lambda.amazonaws.com":
            if event_name == "CreateFunction20150331":
                resource_info["resource_type"] = "lambda:function"
                resource_info["resource_ids"] = [response_elements.get("functionName")]
                resource_info["resource_arn"] = response_elements.get("functionArn")
                resource_info["tags"] = extract_lambda_tags(response_elements)

        elif event_source == "elasticloadbalancing.amazonaws.com":
            if event_name == "CreateLoadBalancer":
                load_balancers = response_elements.get("loadBalancers", [])
                if load_balancers:
                    resource_info["resource_type"] = "elb:loadbalancer"
                    resource_info["resource_ids"] = [lb.get("loadBalancerName") for lb in load_balancers]
                    resource_info["resource_arn"] = load_balancers[0].get("loadBalancerArn")
                    resource_info["tags"] = []

        elif event_source == "autoscaling.amazonaws.com":
            if event_name == "CreateAutoScalingGroup":
                resource_info["resource_type"] = "autoscaling:group"
                resource_info["resource_ids"] = [request_parameters.get("autoScalingGroupName")]
                resource_info["tags"] = extract_asg_tags(request_parameters)

        # Check if we have valid resource info
        if resource_info.get("resource_type") and resource_info.get("resource_ids"):
            return resource_info

        logger.info(f"Unsupported event: {event_source} - {event_name}")
        return None

    except Exception as e:
        logger.error(f"Error extracting resource info: {e}")
        return None


def extract_ec2_tags(instance: dict) -> list[dict]:
    """Extract tags from EC2 instance response."""
    tag_set = instance.get("tagSet", {}).get("items", [])
    return [{"Key": t.get("key"), "Value": t.get("value")} for t in tag_set]


def extract_tags_from_response(response: dict) -> list[dict]:
    """Extract tags from generic response element."""
    tag_set = response.get("tagSet", {}).get("items", [])
    return [{"Key": t.get("key"), "Value": t.get("value")} for t in tag_set]


def extract_rds_tags(db_resource: dict) -> list[dict]:
    """Extract tags from RDS response."""
    tag_list = db_resource.get("tagList", [])
    return [{"Key": t.get("key"), "Value": t.get("value")} for t in tag_list]


def extract_lambda_tags(response: dict) -> list[dict]:
    """Extract tags from Lambda response."""
    tags = response.get("tags", {})
    return [{"Key": k, "Value": v} for k, v in tags.items()]


def extract_asg_tags(params: dict) -> list[dict]:
    """Extract tags from Auto Scaling Group request."""
    tags = params.get("tags", [])
    return [{"Key": t.get("key"), "Value": t.get("value")} for t in tags]


def lambda_handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for tag compliance checking.

    Args:
        event: EventBridge event containing CloudTrail details
        context: Lambda context

    Returns:
        Response dict with status and message
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")

    try:
        # Handle test events
        if event.get("test"):
            logger.info("Test event received")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Test successful"})
            }

        # Extract resource information from the event
        resource_info = extract_resource_info(event)

        if not resource_info:
            logger.info("No actionable resource information found in event")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Event not applicable for tag compliance check"})
            }

        # Skip if marked to skip
        if resource_info.get("skip_check"):
            logger.info(f"Skipping check for {resource_info.get('resource_type')}")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Check skipped"})
            }

        logger.info(f"Processing resource: {resource_info}")

        # Initialize the agent and run compliance check
        agent = TagComplianceAgent()
        result = agent.check_compliance(resource_info)

        logger.info(f"Compliance check result: {result}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Compliance check completed",
                "result": result
            }, default=str)
        }

    except Exception as e:
        logger.error(f"Error processing event: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
