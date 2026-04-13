
Project: AIOps Recommendation and Incident Management Dashboard
Author: Ajay Anitha Ganesan


```markdown
# AIOps Recommendation and Incident Management Dashboard

**Author:** Ajay Anitha Ganesan

---

## 1. OVERVIEW

This project is a serverless AIOps (Artificial Intelligence for IT Operations) dashboard that automatically analyzes AWS error logs, identifies root causes, and provides actionable remediation steps. The system simulates real-world cloud incident management by integrating **5 AWS services programmatically**:

- **DynamoDB** - Stores all incidents with severity, status, root cause, and remediation steps
- **SNS** - Sends email alerts for HIGH and MEDIUM severity incidents
- **CloudWatch** - Tracks incident metrics (total, high, medium, resolved, AI failures)
- **S3** - Archives resolved incidents and generates daily CSV reports
- **SSM Parameter Store** - Securely stores configuration (SNS ARN, S3 bucket name)

The system operates through a modern, responsive HTML/JavaScript dashboard that provides real-time incident monitoring, status updates, and investigation note-taking capabilities.

---

## 2. REQUIRED DEPENDENCIES

### Python Packages (Lambda)
```
boto3>=1.26.0
aiops-log-processor
```

### Runtime Environment
- Python 3.9+ (AWS Lambda runtime)
- AWS CLI (for deployment)

### Frontend
- Modern web browser (Chrome, Firefox, Safari, Edge)
- No additional dependencies - pure HTML/CSS/JavaScript

---

## 3. CONFIGURATION PARAMETERS

### AWS SSM Parameter Store
| Parameter Name | Description |
|----------------|-------------|
| `/aiops/sns_topic_arn` | SNS Topic ARN for email alerts (HIGH/MEDIUM incidents) |
| `/aiops/s3_archive_bucket` | S3 bucket name for archiving resolved incidents and CSV reports |

### Environment Variables (Fallback)
| Variable | Description |
|----------|-------------|
| `SNS_TOPIC_ARN` | Fallback SNS ARN if SSM fetch fails |
| `S3_ARCHIVE_BUCKET` | Fallback S3 bucket name if SSM fetch fails |

### Frontend Configuration
| Variable | Location | Description |
|----------|----------|-------------|
| `DEFAULT_REMOTE_API_URL` | `index.html` (line ~250) | Your Lambda Function URL |
| `POLL_INTERVAL_MS` | `index.html` (line ~282) | Auto-refresh interval (default: 5000ms) |

---

## 4. AWS SERVICES & PERMISSIONS

### Required IAM Permissions for Lambda Role

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:Scan",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem"
            ],
            "Resource": "arn:aws:dynamodb:*:*:table/aiops-incidents"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource": "arn:aws:sns:*:*:your-sns-topic"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::your-bucket/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricData"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/aiops/*"
        }
    ]
}
```

---

## 5. DEPLOYMENT STEPS

### Step 1: Create AWS Resources

1. **DynamoDB Table**
   - Table name: `aiops-incidents`
   - Partition key: `incident_id` (String)
   - Billing mode: Pay per request (or provisioned)

2. **SNS Topic**
   - Create a standard topic (e.g., `aiops-alerts`)
   - Create subscription (Email protocol)
   - Confirm subscription from your email inbox

3. **S3 Bucket**
   - Create a bucket (e.g., `aiops-archive-bucket`)
   - Enable versioning (optional, recommended)
   - Block public access (keep private)

4. **SSM Parameters**
   - Parameter 1: `/aiops/sns_topic_arn` (String, SecureString optional)
   - Parameter 2: `/aiops/s3_archive_bucket` (String)

### Step 2: Deploy Lambda Function

1. **Create Lambda Function**
   - Runtime: Python 3.9+
   - Architecture: x86_64 or arm64
   - Memory: 256 MB (minimum)
   - Timeout: 30 seconds

2. **Attach IAM Role**
   - Create role with permissions from Section 4
   - Attach to Lambda function

3. **Upload Code**
   - Zip the `lambda-package/` folder contents
   - Upload via AWS Console or AWS CLI

4. **Configure Function URL**
   - Auth type: NONE (for demo) or IAM (for production)
   - CORS: Enable with `*` origin (or specific domain)
   - Save the Function URL

### Step 3: Deploy Frontend

1. **Update API URL**
   - Open `index.html`
   - Find `DEFAULT_REMOTE_API_URL` (line ~250)
   - Replace with your Lambda Function URL

2. **Host Frontend**
   - **Option A:** S3 Static Hosting
     ```bash
     aws s3 cp index.html s3://your-bucket/index.html --content-type "text/html"
     ```
   - **Option B:** GitHub Pages
     - Commit `index.html` to a `gh-pages` branch
   - **Option C:** Local Testing
     - Use Live Server extension or Python HTTP server

### Step 4: (Optional) GitHub Actions CI/CD

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Lambda

on:
  push:
    branches: [main]
    paths:
      - 'lambda-package/**'
      - 'index.html'

jobs:
  pylint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install pylint boto3
          pip install -r lambda-package/requirements.txt
      - name: Run pylint
        run: |
          pylint lambda-package/*.py --fail-under=7 --disable=missing-docstring,line-too-long,too-many-arguments,too-many-branches,too-many-statements,too-many-locals,too-many-return-statements,invalid-name,consider-using-f-string,no-name-in-module

  deploy:
    runs-on: ubuntu-latest
    needs: pylint
    steps:
      - uses: actions/checkout@v4
      - name: Create deployment package
        run: |
          cd lambda-package
          zip -r ../deployment_package.zip .
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - name: Update Lambda function
        run: |
          aws lambda update-function-code \
            --function-name aiops-ai-analyzer \
            --zip-file fileb://deployment_package.zip
      - name: Deploy frontend
        run: |
          aws s3 cp index.html s3://${{ secrets.AWS_S3_FRONTEND_BUCKET }}/index.html --content-type "text/html"
```

---

## 6. FEATURES

### Backend (Lambda)

| Feature | Description |
|---------|-------------|
| **Incident Generation** | Randomly selects logs from 155+ error scenarios and analyzes via AI |
| **Severity Classification** | Automatically classifies as HIGH, MEDIUM, LOW, or WARNING |
| **Root Cause Analysis** | AI extracts root cause from log messages |
| **Remediation Steps** | Provides numbered, formatted remediation steps |
| **Email Alerts** | Sends SNS emails for HIGH and MEDIUM severity incidents |
| **Metric Tracking** | CloudWatch metrics for total, high, medium, resolved, and AI failures |
| **S3 Archiving** | Archives resolved incidents as JSON files |
| **CSV Reports** | Generates daily CSV reports of resolved incidents |
| **Status Management** | Update incident status (OPEN, AWAITING_RESOLUTION, RESOLVED) |
| **Notes System** | Add investigation notes to incidents |

### Frontend Dashboard

| Feature | Description |
|---------|-------------|
| **Real-time Summary Cards** | Counts for HIGH, MEDIUM, LOW, WARNING, RESOLVED, AWAITING |
| **Incident Queue** | Sortable table with pagination and status filtering |
| **Incident Details** | View root cause, remediation, log, and notes |
| **Status Updates** | Change incident status with dropdown |
| **Notes Addition** | Add investigation notes with timestamp |
| **Recent Notes Feed** | Shows latest notes across all incidents |
| **Auto-refresh** | Polls API every 5 seconds for updates |
| **Responsive Design** | Works on desktop, tablet, and mobile |

### AI Analysis (via ngrok)

The Lambda calls a local AI endpoint to analyze logs:

```python
# AI expects this request
{
  "log": "ERROR Lambda timed out after 3 seconds"
}

# AI returns this response format
{
  "error_type": "LambdaTimeout",
  "root_cause": "Lambda execution exceeded configured timeout",
  "recommended_fix": "1. Increase Lambda timeout\n2. Optimize code execution\n3. Break into smaller functions",
  "severity": "MEDIUM"
}
```

---

## 7. API ENDPOINTS

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | List all incidents |
| `GET` | `/?action=generate` | Generate a new incident |
| `POST` | `/` | Update incident status/add note |
| `POST` | `/` (with `{"action":"delete"}`) | Delete an incident |
| `DELETE` | `/` | Delete an incident |
| `OPTIONS` | `/` | CORS preflight |

### POST Request Body Examples

**Update Incident:**
```json
{
  "incident_id": "inc-20241201120000-1234",
  "status": "RESOLVED",
  "note": "Fixed by increasing Lambda timeout to 10 seconds"
}
```

**Delete Incident:**
```json
{
  "action": "delete",
  "incident_id": "inc-20241201120000-1234"
}
```

---

## 8. CLOUDWATCH METRICS

| Metric Name | Namespace | Description |
|-------------|-----------|-------------|
| `TotalIncidents` | AIOps-App | Total number of incidents created |
| `HighSeverityIncidents` | AIOps-App | Count of HIGH severity incidents |
| `MediumSeverityIncidents` | AIOps-App | Count of MEDIUM severity incidents |
| `ResolvedIncidents` | AIOps-App | Count of incidents marked RESOLVED |
| `AIFailures` | AIOps-App | Count of AI service failures |

**View Metrics:** CloudWatch Console → Metrics → Custom Namespaces → AIOps-App

---

## 9. TROUBLESHOOTING

### Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| **Frontend shows no incidents** | Check Lambda Function URL CORS settings |
| **SNS emails not arriving** | Verify email subscription is confirmed |
| **Decimal serialization error** | `scrub_decimals()` handles this automatically |
| **AI analysis fails** | Check ngrok tunnel is active and URL is correct |
| **S3 archiving fails** | Verify bucket name and Lambda IAM permissions |

### Testing Locally

1. **Test Lambda function:**
   ```bash
   cd lambda-package
   python -c "import lambda_function; lambda_function.create_incident()"
   ```

2. **Test API locally (using Python HTTP server):**
   ```bash
   python -m http.server 8000
   # Open http://localhost:8000/index.html
   ```

---

## 10. PROJECT STRUCTURE

```
project-root/
├── lambda-package/
│   ├── lambda_function.py          # Main Lambda code
│   ├── requirements.txt             # Python dependencies
│   └── aiops_log_processor/         # Custom module (imported)
│       ├── formatter.py
│       ├── parser.py
│       └── severity.py
├── index.html                       # Frontend dashboard
├── .github/workflows/
│   └── deploy.yml                   # CI/CD pipeline
└── README.md                        # This file
```

---

## 11. LICENSE

This project is for educational and demonstration purposes.

---

**Questions or Issues?** Contact the author or open a GitHub issue.

**Last Updated:** April 2026
```
