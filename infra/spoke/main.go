package main

import (
	"encoding/json"
	"fmt"

	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/cloudwatch"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/iam"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi/config"
)

func main() {
	pulumi.Run(func(ctx *pulumi.Context) error {
		// Get configuration
		cfg := config.New(ctx, "spoke")
		awsCfg := config.New(ctx, "aws")

		// Region configuration
		region := awsCfg.Get("region")
		if region == "" {
			region = "us-east-1"
		}

		// Get current account ID
		callerIdentity, err := aws.GetCallerIdentity(ctx, &aws.GetCallerIdentityArgs{})
		if err != nil {
			return err
		}
		currentAccountId := callerIdentity.AccountId

		// Hub configuration (required)
		hubAccountId := cfg.Require("hubAccountId")
		hubRegion := cfg.Require("hubRegion")
		hubEventBusArn := cfg.Require("hubEventBusArn")

		// Validate configuration
		if hubAccountId == "" || hubRegion == "" || hubEventBusArn == "" {
			return fmt.Errorf("spoke deployment requires hubAccountId, hubRegion, and hubEventBusArn configuration")
		}

		// Create IAM role for EventBridge to assume for cross-account event delivery
		assumeRolePolicy, _ := json.Marshal(map[string]any{
			"Version": "2012-10-17",
			"Statement": []map[string]any{
				{
					"Action": "sts:AssumeRole",
					"Effect": "Allow",
					"Principal": map[string]any{
						"Service": "events.amazonaws.com",
					},
				},
			},
		})

		crossAccountRole, err := iam.NewRole(ctx, "eventbridge-cross-account-role", &iam.RoleArgs{
			Name:             pulumi.String("tag-compliance-eventbridge-cross-account"),
			AssumeRolePolicy: pulumi.String(string(assumeRolePolicy)),
			Tags: pulumi.StringMap{
				"Project":   pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
				"Component": pulumi.String("spoke"),
			},
		})
		if err != nil {
			return err
		}

		// Policy allowing EventBridge to put events to hub account's event bus
		crossAccountPolicy, _ := json.Marshal(map[string]any{
			"Version": "2012-10-17",
			"Statement": []map[string]any{
				{
					"Sid":      "AllowPutEventsToHubBus",
					"Effect":   "Allow",
					"Action":   "events:PutEvents",
					"Resource": hubEventBusArn,
				},
			},
		})

		_, err = iam.NewRolePolicy(ctx, "eventbridge-cross-account-policy", &iam.RolePolicyArgs{
			Role:   crossAccountRole.Name,
			Policy: pulumi.String(string(crossAccountPolicy)),
		})
		if err != nil {
			return err
		}

		// Create EventBridge rule to capture resource creation events
		eventPattern, _ := json.Marshal(map[string]any{
			"source":      []string{"aws.ec2", "aws.s3", "aws.rds", "aws.lambda", "aws.elasticloadbalancing", "aws.autoscaling"},
			"detail-type": []string{"AWS API Call via CloudTrail"},
			"detail": map[string]any{
				"eventSource": []string{
					"ec2.amazonaws.com",
					"s3.amazonaws.com",
					"rds.amazonaws.com",
					"lambda.amazonaws.com",
					"elasticloadbalancing.amazonaws.com",
					"autoscaling.amazonaws.com",
				},
				"eventName": []any{
					map[string]string{"prefix": "Create"},
					map[string]string{"prefix": "Run"},
					map[string]string{"prefix": "Put"},
					"AllocateAddress",
				},
			},
		})

		eventRule, err := cloudwatch.NewEventRule(ctx, "tag-compliance-forward-rule", &cloudwatch.EventRuleArgs{
			Name:         pulumi.String("tag-compliance-forward-to-hub"),
			Description:  pulumi.String("Forward resource creation events to hub account for tag compliance checking"),
			EventPattern: pulumi.String(string(eventPattern)),
			Tags: pulumi.StringMap{
				"Project":   pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
				"Component": pulumi.String("spoke"),
			},
		})
		if err != nil {
			return err
		}

		// Create target to forward events to hub account's event bus
		_, err = cloudwatch.NewEventTarget(ctx, "tag-compliance-hub-target", &cloudwatch.EventTargetArgs{
			Rule:     eventRule.Name,
			TargetId: pulumi.String("hub-event-bus"),
			Arn:      pulumi.String(hubEventBusArn),
			RoleArn:  crossAccountRole.Arn,
		})
		if err != nil {
			return err
		}

		// Export spoke outputs
		ctx.Export("region", pulumi.String(region))
		ctx.Export("accountId", pulumi.String(currentAccountId))
		ctx.Export("eventRuleName", eventRule.Name)
		ctx.Export("eventRuleArn", eventRule.Arn)
		ctx.Export("crossAccountRoleArn", crossAccountRole.Arn)
		ctx.Export("hubAccountId", pulumi.String(hubAccountId))
		ctx.Export("hubRegion", pulumi.String(hubRegion))
		ctx.Export("hubEventBusArn", pulumi.String(hubEventBusArn))

		return nil
	})
}
