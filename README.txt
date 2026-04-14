# AIOps Recommendation and Incident Management Dashboard

**Author:** Ajay Anitha Ganesan

---

## 1. Overview

This project is a serverless CloudOps dashboard that automatically analyzes AWS error logs, identifies root causes, and provides operational remediation steps. The system integrates 5 AWS services programmatically and operates through a modern HTML/JavaScript interface.

**AWS Services Used:**
- DynamoDB - Stores incidents
- SNS - Email alerts for HIGH/MEDIUM severity
- CloudWatch - Incident metrics
- S3 - Archiving resolved incidents and CSV reports
- SQS - Dead letter queue for failed AI processing

---

## 2. Project Structure

```
project-root/
├── lambda-package/
│   ├── lambda_function.py          # Main Lambda code
│   ├── requirements.txt
│   └── aiops_log_processor/         # Local library
│       ├── formatter.py
│       ├── parser.py
│       └── severity.py
├── index.html                       # Frontend dashboard
├── app.py                           # Local AI proxy
└── .github/workflows/deploy.yml
```

---

## 3. Configuration

**SSM Parameter Store:**
| Parameter | Description |
|-----------|-------------|
| `/aiops/sns_topic_arn` | SNS Topic ARN for email alerts |
| `/aiops/s3_archive_bucket` | S3 bucket for archiving |

**Lambda Environment Variables:**
| Variable | Description |
|----------|-------------|
| `NGROK_URL` | Local AI endpoint URL |

---

## 4. Deployment Steps

1. Create DynamoDB table `aiops-incidents` with partition key `incident_id`
2. Create SNS topic and subscribe email address
3. Create S3 bucket for archiving
4. Create SQS queue (disable DLQ, visibility timeout 30 seconds)
5. Add SSM parameters with SNS ARN and S3 bucket name
6. Deploy Lambda with attached IAM role (permissions for DynamoDB, SNS, S3, CloudWatch, SSM, SQS)
7. Enable Lambda Function URL with CORS
8. Upload `index.html` to S3 static hosting
9. Run local AI: `ollama serve` + `uvicorn app:app --reload` + `ngrok http 8000`
10. Update `NGROK_URL` in Lambda

---

## 5. Local AI Setup

```bash
# Terminal 1
ollama serve

# Terminal 2
python -m uvicorn app:app --reload --port 8000

# Terminal 3
ngrok http 8000
```

The AI model used is `phi4-mini:latest`. Update the Lambda's `NGROK_URL` after each ngrok restart.

---

## 6. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all incidents |
| GET | `/?action=generate` | Generate new incident |
| GET | `/?queue_count=true` | Get SQS queue count |
| GET | `/?failed_queue=true` | Get failed incidents from SQS |
| POST | `/` | Update incident status/add note |
| POST | `/` (with `action:retry_failed`) | Retry failed incident |

---

## 7. Features

**Backend:**
- Fetches random logs from GitHub JSON
- Calls local AI for analysis (ngrok + Ollama)
- Classifies severity using keyword matching (timeout, memory exceeded, etc.)
- Stores incidents in DynamoDB
- Sends email alerts for HIGH/MEDIUM severity
- Archives resolved incidents to S3
- Generates daily CSV reports
- Saves failed AI requests to SQS for manual retry

**Frontend:**
- Summary cards with incident counts
- Sortable and filterable incident table
- Status update and notes system
- Recent notes panel with pagination
- Failed queue filter with retry button
- Auto-refresh every 5 seconds (pauses during editing)

---

## 8. Dependencies

**Python packages:**
```
boto3>=1.26.0
```

**Local tools:**
- Ollama (phi4-mini:latest model)
- FastAPI + Uvicorn
- ngrok

---

## 9. CI/CD Pipeline

GitHub Actions workflow runs on push to main:
1. Pylint analysis (errors only, ignores style warnings)
2. Creates deployment package
3. Updates Lambda function code
4. Uploads index.html to S3

---

## 10. License

Educational project.

**Last updated:** April 2026