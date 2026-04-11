# Agentic AI CloudOps Troubleshooting System

## Purpose
This file is our running build tracker for the project described in the shared chat:

- Project direction: `Agentic AI CloudOps Troubleshooting System`
- Core idea: an AI-powered CloudOps assistant that can inspect AWS issues, explain root cause, recommend fixes, and later support safe automated remediation
- Target build environment: `AWS Academy Lab`

We will update this file after every meaningful implementation step so we always know:

- what we built
- why we built it
- which AWS services are involved
- what is complete vs pending
- what still needs testing or cleanup

## Shared Chat Context Summary
The shared project conversation points to a serverless AWS architecture with these main components:

- `Amazon API Gateway` for the public API
- `AWS Lambda` as the agent controller and backend logic
- `Amazon Bedrock` for AI reasoning
- `Amazon CloudWatch` for logs and operational signals
- `Amazon DynamoDB` for incident or ticket history
- optional `Amazon S3` knowledge base / RAG support

The business problem is reducing repetitive cloud troubleshooting work such as:

- EC2 connectivity issues
- Lambda failures and timeouts
- IAM permission problems
- API Gateway errors
- S3 access errors

The intended workflow is:

1. User submits a cloud issue
2. Backend receives request through API Gateway
3. Lambda gathers context or diagnostics
4. Bedrock generates analysis and recommended action
5. System stores the incident and response
6. Later phases may support approved remediation actions

## Current Repository State
Current repo contents:

- `app.py`

Current implementation in `app.py`:

- FastAPI endpoint: `POST /analyze`
- Sends log text to a local `Ollama` model (`phi4-mini:latest`)
- Returns AI analysis response

What this means:

- we already have a small proof of concept for log analysis
- it is not yet aligned with the AWS target architecture
- it uses local inference instead of `Amazon Bedrock`
- it does not yet include API Gateway, Lambda, CloudWatch integration, or DynamoDB storage

## Target Architecture
Planned target architecture for the AWS Academy build:

```text
User / Frontend
    -> API Gateway
    -> Lambda (CloudOps Agent Controller)
    -> Bedrock for reasoning
    -> CloudWatch for logs and diagnostics
    -> DynamoDB for incident history

Optional later:
    -> S3 knowledge base
    -> safe remediation actions through AWS SDK
```

## Implementation Rules
As we build this project, each step should aim to answer:

- What are we creating?
- Why is it needed?
- What AWS service is involved?
- How do we verify it works?
- What is the next dependency?

We should prefer this order in AWS Academy:

1. get a minimal serverless pipeline working
2. replace local AI with Bedrock
3. add logging and storage
4. improve analysis quality
5. add optional remediation only after core workflow is stable

## Step Tracker

### Step 0: Baseline Project Review
Status: `Completed`

What we did:

- reviewed the shared project chat
- identified the target project scope and architecture
- inspected the current repository
- confirmed the current code is a local FastAPI + Ollama proof of concept

Why this step matters:

- it prevents us from building in the wrong direction
- it gives us a clean starting point for AWS Academy implementation

Evidence / notes:

- shared chat title: `Agentic AI CloudOps Solution`
- current code file: `app.py`

---

### Step 0.5: Dashboard Modernization And Incident Update Flow
Status: `Completed`

What we did:

- updated the Lambda to support clean incident listing and explicit incident generation
- improved status handling for `OPEN`, `AWAITING_RESOLUTION`, and `RESOLVED`
- ensured notes are appended and stored permanently in `DynamoDB`
- redesigned the frontend into a modern dashboard with summary cards, visible status badges, and a proper submit action

Why this step matters:

- it makes the project feel like a real operations dashboard instead of a basic demo page
- it gives us a cleaner incident workflow for presentations and testing

Evidence / notes:

- Lambda file: `lambda-package/lambda_function.py`
- UI file: `index.html`

---

### Step 0.6: Reusable PyPI Library Integration
Status: `Completed`

What we did:

- replaced duplicated Lambda helper logic with imports from the reusable `aiops_log_processor` package
- aligned the Lambda flow with the published package responsibilities for parsing, severity classification, and incident formatting
- bundled the package module into the Lambda deployment folder so it can be deployed with the application

Why this step matters:

- it matches the project expectation of creating and using a reusable Python library
- it improves maintainability and keeps the application logic closer to the published package design

Evidence / notes:

- package module path: `lambda-package/aiops_log_processor`
- Lambda file: `lambda-package/lambda_function.py`

---

### Step 0.7: AWS Static Frontend Deployment Preparation
Status: `Completed`

What we did:

- updated the dashboard frontend to choose its API endpoint based on where it is running
- kept `localhost` pointed at the local FastAPI proxy for development
- set non-local deployments to use the deployed Lambda Function URL by default

Why this step matters:

- it lets the same `index.html` work both locally and from an `S3` static website deployment
- it avoids introducing extra hosting complexity like Elastic Beanstalk for a static frontend

Evidence / notes:

- UI file: `index.html`
- deployment target: `S3 static website hosting + Lambda Function URL + DynamoDB`

---

### Step 0.8: Direct Browser To Lambda CORS Cleanup
Status: `Completed`

What we did:

- removed manual `Access-Control-*` headers from the Lambda response
- kept CORS ownership on the Lambda Function URL configuration instead

Why this step matters:

- it avoids duplicate CORS headers when the dashboard is hosted in `S3` and calls the Lambda Function URL directly
- it makes browser-based deployment more stable than the earlier local-proxy-only setup

Evidence / notes:

- Lambda file: `lambda-package/lambda_function.py`
- browser deployment path: `S3 website endpoint -> Lambda Function URL`

---

### Step 0.9: Silent Dashboard Polling
Status: `Completed`

What we did:

- added automatic dashboard polling every `5` seconds
- refreshed the UI only when incident data actually changed
- preserved in-progress note and status edits during background refreshes

Why this step matters:

- it makes the dashboard feel live without adding direct browser access to `DynamoDB`
- it avoids visible blinking or disruptive redraws during normal monitoring

Evidence / notes:

- UI file: `index.html`
- refresh model: `frontend polling -> Lambda Function URL -> DynamoDB`

---

### Step 0.10: SNS Incident Alerting
Status: `Completed`

What we did:

- added optional `Amazon SNS` publishing for newly created `HIGH` severity incidents
- stored SNS alert delivery status in `DynamoDB` so the result is visible in the incident data model
- kept the integration environment-driven through `SNS_TOPIC_ARN` so the application still works when alerts are not configured

Why this step matters:

- it adds another meaningful AWS service programmatically to the application workflow
- it makes the incident dashboard feel more like a real operations escalation system

Evidence / notes:

- Lambda file: `lambda-package/lambda_function.py`
- required configuration: Lambda environment variable `SNS_TOPIC_ARN`
- required IAM permission: `sns:Publish`

---

### Step 1: Define Final MVP Scope
Status: `Pending`

Goal:

- decide the smallest end-to-end version we will build first in AWS Academy

Recommended MVP:

- API Gateway endpoint
- Lambda backend
- Bedrock prompt-based analysis
- CloudWatch logging
- DynamoDB incident storage

Why we are doing this:

- AWS Academy labs are time and credit constrained
- a smaller MVP is easier to deploy, debug, and demo

Definition of done:

- one clearly documented MVP flow is locked
- optional features are explicitly marked out of scope for phase 1

---

### Step 2: Design Request/Response Contract
Status: `Pending`

Goal:

- define what input the system accepts and what output it returns

Planned input example:

```json
{
  "issue_type": "lambda_timeout",
  "service": "lambda",
  "description": "My Lambda function is timing out",
  "logs": "..."
}
```

Planned output example:

```json
{
  "root_cause": "...",
  "severity": "...",
  "recommended_fix": "...",
  "next_action": "..."
}
```

Why we are doing this:

- stable contracts make Lambda logic, API Gateway mapping, and frontend integration easier

Definition of done:

- payload schema documented
- response schema documented

---

### Step 3: Convert Backend from FastAPI PoC to Lambda-Friendly Logic
Status: `Pending`

Goal:

- move reusable analysis logic into a form that can run inside Lambda

Why we are doing this:

- the current app is useful for local experimentation
- AWS Academy deployment should center on Lambda rather than a long-running FastAPI service

Definition of done:

- core analysis function is separated from framework-specific code
- Lambda entrypoint structure is defined

---

### Step 4: Create Bedrock-Based Analysis Layer
Status: `Pending`

Goal:

- replace local Ollama inference with Amazon Bedrock

Why we are doing this:

- Bedrock is part of the intended architecture
- it matches the project pitch and recruiter-facing story

Expected work:

- choose supported Bedrock model in AWS Academy lab
- create prompt template for cloud issue analysis
- handle Bedrock response parsing

Definition of done:

- Lambda can send a request to Bedrock
- response is returned in structured form

---

### Step 5: Deploy API Gateway + Lambda Integration
Status: `Pending`

Goal:

- expose the backend through a serverless API endpoint

Why we are doing this:

- this creates the first true end-to-end AWS version of the project

Definition of done:

- API Gateway invokes Lambda successfully
- test request returns valid JSON response

---

### Step 6: Add CloudWatch Logging
Status: `Pending`

Goal:

- log incoming requests, failures, and analysis results safely

Why we are doing this:

- CloudWatch visibility is essential for debugging and for the CloudOps story

Definition of done:

- Lambda logs are visible in CloudWatch
- key events are easy to trace

---

### Step 7: Add DynamoDB Incident History
Status: `Pending`

Goal:

- persist incidents and generated analysis

Suggested stored fields:

- `incident_id`
- `timestamp`
- `service`
- `issue_type`
- `description`
- `root_cause`
- `severity`
- `recommended_fix`
- `status`

Why we are doing this:

- this turns the system from a one-off chatbot into an operational support assistant

Definition of done:

- each request creates or updates a DynamoDB record

---

### Step 8: Improve Prompting for Cloud Troubleshooting Quality
Status: `Pending`

Goal:

- make responses more useful, consistent, and demo-ready

Expected improvements:

- force structured analysis sections
- classify severity consistently
- require a root cause and recommendation
- include confidence or limitations when signal is weak

Definition of done:

- prompts are versioned and documented
- responses are more predictable across example issues

---

### Step 9: Add Curated Sample Incident Inputs
Status: `Pending`

Goal:

- prepare realistic demo cases for EC2, Lambda, IAM, API Gateway, and S3

Why we are doing this:

- demo quality matters for presentation, portfolio use, and debugging

Definition of done:

- sample payloads exist for multiple issue types
- each sample has an expected output pattern

---

### Step 10: Optional Safe Remediation Layer
Status: `Pending`

Goal:

- support approved corrective actions after analysis is stable

Examples:

- update Lambda timeout
- suggest or stage security group rule changes
- trigger a controlled diagnostic action

Important note:

- this should come only after the analysis path is working well
- remediation in AWS Academy should stay conservative and reversible

Definition of done:

- at least one remediation flow is implemented safely
- permissions are tightly scoped

---

### Step 11: Optional Knowledge Base / RAG Support
Status: `Pending`

Goal:

- enrich answers with AWS troubleshooting reference material

Possible storage:

- `S3` for documents

Why we may add this later:

- useful, but not required for MVP
- adds complexity beyond the core agent workflow

Definition of done:

- system can retrieve supporting guidance for known cloud errors

---

### Step 12: Final Demo and Documentation
Status: `Pending`

Goal:

- prepare the project for presentation and resume use

Expected outputs:

- final architecture diagram
- setup guide
- demo script
- screenshots
- short project summary for resume / portfolio

Definition of done:

- project can be explained, demonstrated, and reused cleanly

## Build Log Template
Use this section for real implementation updates as we go.

### Update Entry Template

```text
Date:
Step:
Status:

What we implemented:
- ...

Why we implemented it:
- ...

AWS services touched:
- ...

Files changed:
- ...

Validation:
- ...

Open issues / next step:
- ...
```

## First Recommended Build Sequence
This is the order I recommend we follow in the AWS Academy lab:

1. Lock MVP scope
2. Refactor current analysis code for Lambda use
3. Build Lambda handler
4. Connect Lambda to Bedrock
5. Put API Gateway in front
6. Add CloudWatch logging
7. Add DynamoDB persistence
8. Test with sample incidents
9. Add optional remediation
10. Add optional knowledge base

## Notes For Future Updates
- Update this file immediately after each completed step.
- If we change architecture, update both the relevant step and the target architecture section.
- If AWS Academy limits a service or feature, record the constraint here rather than relying on memory.
- If we make a shortcut for lab/demo reasons, document it clearly.
