package main

import (
	"archive/zip"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/cloudwatch"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/dynamodb"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/iam"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/lambda"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/sns"
	"github.com/pulumi/pulumi-command/sdk/go/command/local"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi/config"
)

// ensurePlaceholderZip creates an empty placeholder zip file if it doesn't exist.
// This allows Pulumi to evaluate FileArchive during planning before the build runs.
func ensurePlaceholderZip(zipPath string) error {
	// Get absolute path
	absPath, err := filepath.Abs(zipPath)
	if err != nil {
		return err
	}

	// Check if file exists
	if _, err := os.Stat(absPath); err == nil {
		return nil // File exists, nothing to do
	}

	// Create directory if needed
	dir := filepath.Dir(absPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	// Create empty zip file
	file, err := os.Create(absPath)
	if err != nil {
		return err
	}
	defer file.Close()

	// Write minimal valid zip structure
	zipWriter := zip.NewWriter(file)
	return zipWriter.Close()
}

func main() {
	// Ensure placeholder zip exists before Pulumi evaluates FileArchive
	if err := ensurePlaceholderZip("../../lambda/function.zip"); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: could not create placeholder zip: %v\n", err)
	}

	pulumi.Run(func(ctx *pulumi.Context) error {
		// Get configuration
		cfg := config.New(ctx, "hub")
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

		// Configuration
		spokeAccountIds := cfg.Get("spokeAccountIds")
		bedrockModelId := cfg.Get("bedrockModelId")
		if bedrockModelId == "" {
			bedrockModelId = "amazon.nova-2-lite-v1:0"
		}
		lambdaArchitecture := cfg.Get("lambdaArchitecture")
		if lambdaArchitecture == "" {
			lambdaArchitecture = "arm64"
		}
		lambdaMemory := cfg.GetInt("lambdaMemory")
		if lambdaMemory == 0 {
			lambdaMemory = 512
		}
		lambdaTimeout := cfg.GetInt("lambdaTimeout")
		if lambdaTimeout == 0 {
			lambdaTimeout = 60
		}

		// Build Lambda package automatically
		// Determine platform based on architecture
		// Using manylinux_2_28 for Amazon Linux 2023 (glibc 2.34) compatibility
		platform := "manylinux_2_28_aarch64"
		if lambdaArchitecture == "x86_64" {
			platform = "manylinux_2_28_x86_64"
		}

		buildScript := fmt.Sprintf(`#!/bin/bash
set -e
cd ../../lambda

# Create and activate virtual environment using Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# Clean previous build
rm -rf package function.zip

# Install dependencies for Lambda architecture
# --ignore-requires-python: local Python is 3.9 but Lambda uses 3.12
pip install \
  --platform %s \
  --target ./package \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --ignore-requires-python \
  strands-agents strands-agents-tools requests typing-extensions

# Create deployment zip
cd package && zip -rq ../function.zip . && cd ..
zip -gq function.zip handler.py agent.py
zip -grq function.zip tools/

echo "Lambda package built: $(ls -lh function.zip | awk '{print $5}')"
`, platform)

		buildLambda, err := local.NewCommand(ctx, "build-lambda", &local.CommandArgs{
			Create: pulumi.String(buildScript),
			Triggers: pulumi.Array{
				// Rebuild when source files change
				pulumi.String("../../lambda/handler.py"),
				pulumi.String("../../lambda/agent.py"),
				pulumi.String("../../lambda/requirements.txt"),
				pulumi.String("../../lambda/tools/"),
			},
		})
		if err != nil {
			return err
		}

		// Create custom EventBridge bus for receiving events from spoke accounts
		eventBus, err := cloudwatch.NewEventBus(ctx, "tag-compliance-event-bus", &cloudwatch.EventBusArgs{
			Name: pulumi.String("tag-compliance-events"),
			Tags: pulumi.StringMap{
				"Project":   pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
				"Component": pulumi.String("hub"),
			},
		})
		if err != nil {
			return err
		}

		// Create resource-based policy to allow spoke accounts to send events
		if spokeAccountIds != "" {
			spokeAccounts := strings.Split(spokeAccountIds, ",")
			var principals []string
			for _, accountId := range spokeAccounts {
				accountId = strings.TrimSpace(accountId)
				if accountId != "" {
					principals = append(principals, fmt.Sprintf("arn:aws:iam::%s:root", accountId))
				}
			}

			if len(principals) > 0 {
				busPolicy, _ := json.Marshal(map[string]any{
					"Version": "2012-10-17",
					"Statement": []map[string]any{
						{
							"Sid":    "AllowSpokeAccountsPutEvents",
							"Effect": "Allow",
							"Principal": map[string]any{
								"AWS": principals,
							},
							"Action":   "events:PutEvents",
							"Resource": fmt.Sprintf("arn:aws:events:%s:%s:event-bus/tag-compliance-events", region, currentAccountId),
						},
					},
				})

				_, err = cloudwatch.NewEventBusPolicy(ctx, "tag-compliance-bus-policy", &cloudwatch.EventBusPolicyArgs{
					EventBusName: eventBus.Name,
					Policy:       pulumi.String(string(busPolicy)),
				})
				if err != nil {
					return err
				}
			}
		}

		// Create SNS topic for notifications
		snsTopic, err := sns.NewTopic(ctx, "tag-compliance-notifications", &sns.TopicArgs{
			Name:        pulumi.String("tag-compliance-notifications"),
			DisplayName: pulumi.String("Tag Compliance Violations"),
			Tags: pulumi.StringMap{
				"Project":   pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
			},
		})
		if err != nil {
			return err
		}

		// Create DynamoDB table for tag rules
		rulesTable, err := dynamodb.NewTable(ctx, "tag-compliance-rules", &dynamodb.TableArgs{
			Name:        pulumi.String("TagComplianceRules"),
			BillingMode: pulumi.String("PAY_PER_REQUEST"),
			HashKey:     pulumi.String("ruleId"),
			Attributes: dynamodb.TableAttributeArray{
				&dynamodb.TableAttributeArgs{
					Name: pulumi.String("ruleId"),
					Type: pulumi.String("S"),
				},
			},
			Tags: pulumi.StringMap{
				"Project":   pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
			},
		})
		if err != nil {
			return err
		}

		// Create CloudWatch Log Group for Lambda
		logGroup, err := cloudwatch.NewLogGroup(ctx, "tag-compliance-logs", &cloudwatch.LogGroupArgs{
			Name:            pulumi.String("/aws/lambda/tag-compliance-checker"),
			RetentionInDays: pulumi.Int(14),
			Tags: pulumi.StringMap{
				"Project":   pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
			},
		})
		if err != nil {
			return err
		}

		// Create IAM role for Lambda
		assumeRolePolicy, _ := json.Marshal(map[string]any{
			"Version": "2012-10-17",
			"Statement": []map[string]any{
				{
					"Action": "sts:AssumeRole",
					"Effect": "Allow",
					"Principal": map[string]any{
						"Service": "lambda.amazonaws.com",
					},
				},
			},
		})

		lambdaRole, err := iam.NewRole(ctx, "tag-compliance-lambda-role", &iam.RoleArgs{
			Name:             pulumi.String("tag-compliance-lambda-role"),
			AssumeRolePolicy: pulumi.String(string(assumeRolePolicy)),
			Tags: pulumi.StringMap{
				"Project":   pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
			},
		})
		if err != nil {
			return err
		}

		// Lambda basic execution policy
		_, err = iam.NewRolePolicyAttachment(ctx, "lambda-basic-execution", &iam.RolePolicyAttachmentArgs{
			Role:      lambdaRole.Name,
			PolicyArn: pulumi.String("arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"),
		})
		if err != nil {
			return err
		}

		// Custom policy for Bedrock, DynamoDB, SNS, and resource tag operations
		customPolicy := pulumi.All(rulesTable.Arn, snsTopic.Arn).ApplyT(func(args []any) (string, error) {
			tableArn := args[0].(string)
			topicArn := args[1].(string)
			policy, _ := json.Marshal(map[string]any{
				"Version": "2012-10-17",
				"Statement": []map[string]any{
					{
						"Sid":    "BedrockInvoke",
						"Effect": "Allow",
						"Action": []string{
							"bedrock:InvokeModel",
							"bedrock:InvokeModelWithResponseStream",
						},
						"Resource": "*",
					},
					{
						"Sid":    "DynamoDBRead",
						"Effect": "Allow",
						"Action": []string{
							"dynamodb:GetItem",
							"dynamodb:Scan",
							"dynamodb:Query",
						},
						"Resource": tableArn,
					},
					{
						"Sid":    "SNSPublish",
						"Effect": "Allow",
						"Action": []string{
							"sns:Publish",
						},
						"Resource": topicArn,
					},
					{
						"Sid":    "ResourceTagging",
						"Effect": "Allow",
						"Action": []string{
							"ec2:DescribeTags",
							"ec2:DescribeInstances",
							"ec2:DescribeVolumes",
							"s3:GetBucketTagging",
							"s3:ListBucket",
							"rds:DescribeDBInstances",
							"rds:ListTagsForResource",
							"lambda:GetFunction",
							"lambda:ListTags",
							"elasticloadbalancing:DescribeTags",
							"autoscaling:DescribeTags",
							"tag:GetResources",
							"tag:GetTagKeys",
							"tag:GetTagValues",
						},
						"Resource": "*",
					},
				},
			})
			return string(policy), nil
		}).(pulumi.StringOutput)

		_, err = iam.NewRolePolicy(ctx, "tag-compliance-lambda-policy", &iam.RolePolicyArgs{
			Role:   lambdaRole.Name,
			Policy: customPolicy,
		})
		if err != nil {
			return err
		}

		// Create Lambda function
		lambdaFunc, err := lambda.NewFunction(ctx, "tag-compliance-checker", &lambda.FunctionArgs{
			Name:       pulumi.String("tag-compliance-checker"),
			Runtime:    pulumi.String("python3.12"),
			Handler:    pulumi.String("handler.lambda_handler"),
			Role:       lambdaRole.Arn,
			MemorySize: pulumi.Int(lambdaMemory),
			Timeout:    pulumi.Int(lambdaTimeout),
			Architectures: pulumi.StringArray{
				pulumi.String(lambdaArchitecture),
			},
			Code: pulumi.NewFileArchive("../../lambda/function.zip"),
			Environment: &lambda.FunctionEnvironmentArgs{
				Variables: pulumi.StringMap{
					"BEDROCK_MODEL_ID": pulumi.String(bedrockModelId),
					"RULES_TABLE_NAME": rulesTable.Name,
					"SNS_TOPIC_ARN":    snsTopic.Arn,
					"LOG_LEVEL":        pulumi.String("INFO"),
					"PYTHONPATH":       pulumi.String("/var/task"),
				},
			},
			Tags: pulumi.StringMap{
				"Project":   pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
			},
		}, pulumi.DependsOn([]pulumi.Resource{logGroup, buildLambda}))
		if err != nil {
			return err
		}

		// Create EventBridge rule on custom bus for resource creation events
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

		// Rule on custom event bus (receives events from spoke accounts)
		eventRule, err := cloudwatch.NewEventRule(ctx, "tag-compliance-rule", &cloudwatch.EventRuleArgs{
			Name:         pulumi.String("tag-compliance-resource-creation"),
			EventBusName: eventBus.Name,
			Description:  pulumi.String("Capture AWS resource creation events for tag compliance checking"),
			EventPattern: pulumi.String(string(eventPattern)),
			Tags: pulumi.StringMap{
				"Project":   pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
			},
		})
		if err != nil {
			return err
		}

		// Grant EventBridge permission to invoke Lambda
		_, err = lambda.NewPermission(ctx, "eventbridge-invoke-lambda", &lambda.PermissionArgs{
			Action:    pulumi.String("lambda:InvokeFunction"),
			Function:  lambdaFunc.Name,
			Principal: pulumi.String("events.amazonaws.com"),
			SourceArn: eventRule.Arn,
		})
		if err != nil {
			return err
		}

		// Create EventBridge target on custom bus
		_, err = cloudwatch.NewEventTarget(ctx, "tag-compliance-target", &cloudwatch.EventTargetArgs{
			Rule:         eventRule.Name,
			EventBusName: eventBus.Name,
			TargetId:     pulumi.String("tag-compliance-lambda"),
			Arn:          lambdaFunc.Arn,
		})
		if err != nil {
			return err
		}

		// Export hub outputs
		ctx.Export("region", pulumi.String(region))
		ctx.Export("accountId", pulumi.String(currentAccountId))
		ctx.Export("eventBusName", eventBus.Name)
		ctx.Export("eventBusArn", eventBus.Arn)
		ctx.Export("lambdaFunctionName", lambdaFunc.Name)
		ctx.Export("lambdaFunctionArn", lambdaFunc.Arn)
		ctx.Export("dynamoDBTableName", rulesTable.Name)
		ctx.Export("dynamoDBTableArn", rulesTable.Arn)
		ctx.Export("snsTopicName", snsTopic.Name)
		ctx.Export("snsTopicArn", snsTopic.Arn)
		ctx.Export("eventRuleName", eventRule.Name)
		ctx.Export("eventRuleArn", eventRule.Arn)
		ctx.Export("logGroupName", logGroup.Name)
		ctx.Export("bedrockModelId", pulumi.String(bedrockModelId))

		return nil
	})
}
