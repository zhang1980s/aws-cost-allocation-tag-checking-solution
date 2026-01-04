package main

import (
	"encoding/json"
	"fmt"

	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/cloudwatch"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/dynamodb"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/iam"
	"github.com/pulumi/pulumi-aws/sdk/v6/go/aws/lambda"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi/config"
)

func main() {
	pulumi.Run(func(ctx *pulumi.Context) error {
		// Get configuration
		cfg := config.New(ctx, "tagCompliance")

		// Region configuration - can be set via tagCompliance:region or aws:region
		region := cfg.Get("region")
		if region == "" {
			awsCfg := config.New(ctx, "aws")
			region = awsCfg.Get("region")
		}
		if region == "" {
			region = "us-east-1"
		}

		bedrockModelId := cfg.Get("bedrockModelId")
		if bedrockModelId == "" {
			bedrockModelId = "amazon.nova-2-lite-v1:0"
		}
		larkSecretName := cfg.Get("larkSecretName")
		if larkSecretName == "" {
			larkSecretName = "tag-compliance/lark-credentials"
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
				"Project": pulumi.String("TagCompliance"),
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
				"Project": pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
			},
		})
		if err != nil {
			return err
		}

		// Create IAM role for Lambda
		assumeRolePolicy, _ := json.Marshal(map[string]interface{}{
			"Version": "2012-10-17",
			"Statement": []map[string]interface{}{
				{
					"Action": "sts:AssumeRole",
					"Effect": "Allow",
					"Principal": map[string]interface{}{
						"Service": "lambda.amazonaws.com",
					},
				},
			},
		})

		lambdaRole, err := iam.NewRole(ctx, "tag-compliance-lambda-role", &iam.RoleArgs{
			Name:             pulumi.String("tag-compliance-lambda-role"),
			AssumeRolePolicy: pulumi.String(string(assumeRolePolicy)),
			Tags: pulumi.StringMap{
				"Project": pulumi.String("TagCompliance"),
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

		// Custom policy for Bedrock, DynamoDB, Secrets Manager, and resource tag operations
		customPolicy := pulumi.All(rulesTable.Arn).ApplyT(func(args []interface{}) (string, error) {
			tableArn := args[0].(string)
			policy, _ := json.Marshal(map[string]interface{}{
				"Version": "2012-10-17",
				"Statement": []map[string]interface{}{
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
						"Sid":    "SecretsManagerRead",
						"Effect": "Allow",
						"Action": []string{
							"secretsmanager:GetSecretValue",
						},
						"Resource": fmt.Sprintf("arn:aws:secretsmanager:%s:*:secret:%s*", region, larkSecretName),
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
			Name:         pulumi.String("tag-compliance-checker"),
			Runtime:      pulumi.String("python3.12"),
			Handler:      pulumi.String("handler.lambda_handler"),
			Role:         lambdaRole.Arn,
			MemorySize:   pulumi.Int(lambdaMemory),
			Timeout:      pulumi.Int(lambdaTimeout),
			Architectures: pulumi.StringArray{
				pulumi.String(lambdaArchitecture),
			},
			Code: pulumi.NewFileArchive("../lambda/function.zip"),
			Environment: &lambda.FunctionEnvironmentArgs{
				Variables: pulumi.StringMap{
					"BEDROCK_MODEL_ID":  pulumi.String(bedrockModelId),
					"RULES_TABLE_NAME":  rulesTable.Name,
					"LARK_SECRET_NAME":  pulumi.String(larkSecretName),
					"LOG_LEVEL":         pulumi.String("INFO"),
					"PYTHONPATH":        pulumi.String("/var/task"),
				},
			},
			Tags: pulumi.StringMap{
				"Project": pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
			},
		}, pulumi.DependsOn([]pulumi.Resource{logGroup}))
		if err != nil {
			return err
		}

		// Create EventBridge rule for resource creation events
		eventPattern, _ := json.Marshal(map[string]interface{}{
			"source":      []string{"aws.ec2", "aws.s3", "aws.rds", "aws.lambda", "aws.elasticloadbalancing", "aws.autoscaling"},
			"detail-type": []string{"AWS API Call via CloudTrail"},
			"detail": map[string]interface{}{
				"eventSource": []string{
					"ec2.amazonaws.com",
					"s3.amazonaws.com",
					"rds.amazonaws.com",
					"lambda.amazonaws.com",
					"elasticloadbalancing.amazonaws.com",
					"autoscaling.amazonaws.com",
				},
				"eventName": []interface{}{
					map[string]string{"prefix": "Create"},
					map[string]string{"prefix": "Run"},
					map[string]string{"prefix": "Put"},
					"AllocateAddress",
				},
			},
		})

		eventRule, err := cloudwatch.NewEventRule(ctx, "tag-compliance-rule", &cloudwatch.EventRuleArgs{
			Name:         pulumi.String("tag-compliance-resource-creation"),
			Description:  pulumi.String("Capture AWS resource creation events for tag compliance checking"),
			EventPattern: pulumi.String(string(eventPattern)),
			Tags: pulumi.StringMap{
				"Project": pulumi.String("TagCompliance"),
				"ManagedBy": pulumi.String("Pulumi"),
			},
		})
		if err != nil {
			return err
		}

		// Grant EventBridge permission to invoke Lambda
		_, err = lambda.NewPermission(ctx, "eventbridge-invoke-lambda", &lambda.PermissionArgs{
			Action:       pulumi.String("lambda:InvokeFunction"),
			Function:     lambdaFunc.Name,
			Principal:    pulumi.String("events.amazonaws.com"),
			SourceArn:    eventRule.Arn,
		})
		if err != nil {
			return err
		}

		// Create EventBridge target
		_, err = cloudwatch.NewEventTarget(ctx, "tag-compliance-target", &cloudwatch.EventTargetArgs{
			Rule:     eventRule.Name,
			TargetId: pulumi.String("tag-compliance-lambda"),
			Arn:      lambdaFunc.Arn,
		})
		if err != nil {
			return err
		}

		// Export outputs
		ctx.Export("region", pulumi.String(region))
		ctx.Export("lambdaFunctionName", lambdaFunc.Name)
		ctx.Export("lambdaFunctionArn", lambdaFunc.Arn)
		ctx.Export("dynamoDBTableName", rulesTable.Name)
		ctx.Export("dynamoDBTableArn", rulesTable.Arn)
		ctx.Export("eventRuleName", eventRule.Name)
		ctx.Export("eventRuleArn", eventRule.Arn)
		ctx.Export("logGroupName", logGroup.Name)
		ctx.Export("bedrockModelId", pulumi.String(bedrockModelId))

		return nil
	})
}
