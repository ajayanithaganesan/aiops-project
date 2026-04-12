Project: Agentic AI CloudOps Troubleshooting System
Author: Ajay Anitha Ganesan

---------------------------------------------------------
1. OVERVIEW
---------------------------------------------------------
This project is a serverless CloudOps dashboard that analyzes AWS error logs, identifies root causes, and provides operational remediation steps. It strictly satisfies the 5 programmatic AWS service requirements (DynamoDB, SNS, CloudWatch, S3, SSM) while operating through a seamless, modern HTML/JS interface.

---------------------------------------------------------
2. REQUIRED DEPENDENCIES
---------------------------------------------------------
- Python 3.10+
- boto3
- requests
- fastapi (for local emulator testing only)
- uvicorn (for local emulator testing only)

---------------------------------------------------------
3. CONFIGURATION PARAMETERS
---------------------------------------------------------
AWS Systems Manager (SSM) Parameter Store:
- /aiops/sns_topic_arn     : Stores the target ARN for high-severity SNS email alerts
- /aiops/s3_archive_bucket : Stores the S3 bucket name for archiving resolved incidents

Environment Variables (Lambda Fallbacks):
- SNS_TOPIC_ARN
- S3_ARCHIVE_BUCKET

---------------------------------------------------------
4. DEPLOYMENT STEPS
---------------------------------------------------------
1. Create a DynamoDB table named 'aiops-incidents' with partition key 'incident_id' (String).
2. Set up an SNS Topic for alerts and subscribe your email address.
3. Create an S3 Bucket exclusively for logging archives.
4. Add your exact SNS ARN and S3 Bucket Name strings into the AWS SSM Parameter Store.
5. Create a Lambda function using the code in the 'lambda-package' folder. Attach an execution role permitting explicit DynamoDB, CloudWatch, SNS, S3, and SSM access.
6. Enable a Lambda Function URL with CORS allowed for '*' origins.
7. Open 'index.html' and paste the active Lambda Function URL into the DEFAULT_REMOTE_API_URL variable.
8. Upload 'index.html' to an S3 static deployment bucket (or your GitHub Actions pipeline).
9. (Optional) Configure an EventBridge schedule rule to pass a constant JSON `{"action": "generate", "source": "aws.events"}` to the Lambda every 5 minutes to simulate active incoming incidents automatically.
