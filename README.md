# 🤖 AIOps Recommendation and Incident Management Dashboard

> A serverless AWS incident-management dashboard that analyses operational logs, creates actionable incidents, notifies responders, and preserves recovery and reporting data across a managed cloud workflow.

**Author:** Ajay Anitha Ganesan  
**Status:** ✅ Completed academic cloud-platform project  
**Deployment model:** ☁️ Static S3 dashboard + AWS Lambda Function URL

## 🏗️ Architecture

![AIOps dashboard architecture](docs/AIOps%20Dashboard%20Architecture%20Diagram.png)

```text
S3 Static Dashboard
        |
        v
Lambda Function URL --> AWS Lambda --> DynamoDB
                             |  |  |  |  |  |
                             |  |  |  |  |  +--> SSM Parameter Store
                             |  |  |  |  +-----> SQS failure queue
                             |  |  |  +--------> S3 incident archives and CSV reports
                             |  |  +-----------> CloudWatch custom metrics
                             |  +--------------> SNS email alerts
                             +-----------------> ngrok --> FastAPI --> Ollama

EventBridge schedule --> Lambda --> resolved-incident CSV report in S3
```

## ✨ What It Does

| Capability | Implementation |
|---|---|
| AI incident triage | Sends a sampled operational log to a local Ollama model through a FastAPI/ngrok endpoint and parses structured findings. |
| Incident lifecycle | Creates, lists, updates, resolves, retries, and deletes incident records. |
| Operational dashboard | Shows severity and status summaries, an incident queue, investigation notes, failed-analysis items, and a silent five-second refresh. |
| Escalation | Publishes SNS email notifications for `HIGH` and `MEDIUM` incidents. |
| Recovery | Places AI-analysis failures in SQS so an operator can retry them from the dashboard. |
| Audit and reporting | Archives resolved incidents as JSON and writes resolved-incident CSV reports to S3. |
| Observability | Publishes custom CloudWatch metrics for incident volume, severity, resolution, and AI failures. |

## ☁️ AWS Services

| Service | Purpose in this application | Programmatic use |
|---|---|---|
| AWS Lambda | Serverless API and workflow orchestrator | Handles dashboard requests, scheduled reporting, incident processing, and integrations. |
| Amazon DynamoDB | Incident system of record | Stores incident details, status, notes, and SNS delivery metadata. |
| Amazon SNS | Incident escalation | Sends email notifications for `HIGH` and `MEDIUM` severity incidents. |
| Amazon CloudWatch | Application observability | Receives custom metrics including `TotalIncidents`, severity counts, `ResolvedIncidents`, and `AIFailures`. |
| Amazon S3 | Static hosting and durable artifacts | Hosts the dashboard and stores resolved-incident JSON archives and CSV reports. |
| Amazon SQS | Failure recovery queue | Holds failed AI-analysis requests and supports controlled retries. |
| AWS Systems Manager Parameter Store | Runtime configuration | Supplies the AI URL, sample-log URL, SNS topic ARN, S3 bucket, and SQS queue URL. |
| Amazon EventBridge | Scheduled automation | Triggers the Lambda reporting path for periodic resolved-incident CSV generation. |

## 📁 Project Structure

```text
aiops/
|-- index.html                                  # S3-hosted dashboard
|-- app.py                                      # Local FastAPI endpoint for Ollama analysis
|-- docs/
|   `-- AIOps Dashboard Architecture Diagram.png # Architecture diagram used above
|-- lambda-package/
|   |-- lambda_function.py                      # Lambda API and AWS integrations
|   `-- aiops_log_processor/                    # Reusable Python library
|       |-- formatter.py                         # Incident record construction
|       |-- parser.py                            # AI response parsing
|       `-- severity.py                          # Severity classification
`-- .github/workflows/deploy.yml                # CI/CD workflow
```

## 📦 Reusable Library

The Lambda imports the published `aiops_log_processor` library to keep domain logic separate from AWS orchestration.

| Module | Responsibility |
|---|---|
| `formatter.py` | Builds a consistent incident record with a unique identifier and default workflow status. |
| `parser.py` | Extracts error type, severity, root cause, and recommended fix from AI output. |
| `severity.py` | Classifies incident severity from operational-error signals. |

## 🔌 API

The S3 dashboard calls the Lambda Function URL directly. CORS is configured on the Lambda Function URL.

| Method | Request | Purpose |
|---|---|---|
| `GET` | `/` | List all persisted incidents. |
| `GET` | `/?action=generate` | Analyse a sampled log and create an incident. |
| `GET` | `/?queue_count=true` | Return the approximate number of failed AI requests in SQS. |
| `GET` | `/?failed_queue=true` | Return failed AI-analysis messages for review and retry. |
| `POST` | `{ incident_id, status, note }` | Update incident status and append a permanent DynamoDB note. |
| `POST` | `{ action: "retry_failed", ... }` | Re-run AI analysis for an SQS failure and update its incident. |
| `POST` | `{ action: "delete", incident_id }` | Delete an incident record. |

## ⚙️ Configuration

Runtime configuration is read from Parameter Store first, with Lambda environment variables as fallbacks.

| SSM parameter | Fallback environment variable | Description |
|---|---|---|
| `/aiops/ngrok_url` | `NGROK_URL` | Public ngrok URL of the local FastAPI AI endpoint. |
| `/aiops/log_api` | `LOG_API` | Source URL for JSON sample logs. |
| `/aiops/sns_topic_arn` | `SNS_TOPIC_ARN` | SNS topic ARN for incident email alerts. |
| `/aiops/s3_archive_bucket` | `S3_ARCHIVE_BUCKET` | Bucket for resolved-incident archives and reports. |
| `/aiops/sqs_queue_url` | `SQS_QUEUE_URL` | Queue URL for failed AI-analysis requests. |

## 🧠 Local AI Service

The project uses `phi4-mini:latest` through Ollama. Keep this service and its ngrok tunnel running while generating incidents from the deployed dashboard.

```bash
# Terminal 1
ollama serve

# Terminal 2
python -m uvicorn app:app --reload --port 8000

# Terminal 3
ngrok http 8000
```

Update `/aiops/ngrok_url` in SSM Parameter Store after restarting ngrok if the public URL changes.

## 🚀 Deployment

| Step | Action |
|---|---|
| 1 | Create the DynamoDB table `aiops-incidents` with `incident_id` as the partition key. |
| 2 | Create and confirm an SNS email subscription. |
| 3 | Create an S3 bucket for archives/reports and a separate S3 static-hosting bucket for the dashboard if preferred. |
| 4 | Create an SQS queue for failed AI-analysis messages. |
| 5 | Create the SSM parameters listed above. |
| 6 | Grant the Lambda execution role least-privilege access to DynamoDB, SNS, S3, SQS, SSM, and CloudWatch. |
| 7 | Package `lambda_function.py` with `aiops_log_processor`, then deploy it with handler `lambda_function.lambda_handler`. |
| 8 | Configure the Lambda Function URL with `GET`, `POST`, and `OPTIONS` CORS access. |
| 9 | Upload `index.html` to the S3 static website bucket. |
| 10 | Configure the EventBridge schedule to invoke the Lambda report-generation flow. |

## 🔄 CI/CD

The GitHub Actions workflow in `.github/workflows/deploy.yml` runs on pushes to `main` affecting the Lambda, dashboard, or workflow configuration.

| Stage | Outcome |
|---|---|
| Quality gate | Runs Pylint on the Lambda package. |
| Package | Builds a Lambda deployment ZIP. |
| Backend deploy | Updates the `aiops-ai-analyzer` Lambda function. |
| Frontend deploy | Uploads `index.html` to the configured S3 bucket. |

Required GitHub repository secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, and `AWS_S3_FRONTEND_BUCKET`.

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript |
| API and workflow | AWS Lambda Function URL, Python, boto3 |
| Data | Amazon DynamoDB, Amazon S3, Amazon SQS |
| Monitoring and alerts | Amazon CloudWatch, Amazon SNS |
| Configuration and scheduling | AWS Systems Manager Parameter Store, Amazon EventBridge |
| AI analysis | Ollama `phi4-mini:latest`, FastAPI, ngrok |
| Automation | GitHub Actions |

## 📝 Notes

This is an educational cloud-platform project. The AI inference component is intentionally separated from AWS hosting and persistence so it can be replaced by a managed model service when available.

**Last updated:** September 2026
