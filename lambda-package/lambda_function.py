"""AIOps Lambda Function - Recommendation & Incident Management System"""

import datetime
import json
import os
import random
import urllib.request
import csv
import io
import decimal
import re
import requests

import boto3
from aiops_log_processor.formatter import build_incident
from aiops_log_processor.parser import extract_from_text
from aiops_log_processor.severity import classify_severity

# Connecting to AWS services
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")
s3 = boto3.client("s3")
cloudwatch = boto3.client('cloudwatch')
ssm = boto3.client("ssm")

# Our DynamoDB table to store Incident data
table = dynamodb.Table("aiops-incidents")

# Getting configuration from AWS SSM service
def get_ssm_parameter(name, fallback_env):
    try:
        response = ssm.get_parameter(Name=name, WithDecryption=False)
        return response["Parameter"]["Value"].strip()
    except Exception:
        return os.environ.get(fallback_env, "").strip()

# Grok API Configuration
GROK_API_KEY = os.environ.get("GROK_API_KEY", "")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# Configuration values
LOG_API = "https://raw.githubusercontent.com/ajayanithaganesan/aiops-log-data/main/logs.json"
SNS_TOPIC_ARN = get_ssm_parameter("/aiops/sns_topic_arn", "SNS_TOPIC_ARN")
S3_ARCHIVE_BUCKET = get_ssm_parameter("/aiops/s3_archive_bucket", "S3_ARCHIVE_BUCKET")

# Fixing Decimal numbers for JSON
def scrub_decimals(data):
    if isinstance(data, list):
        return [scrub_decimals(i) for i in data]
    if isinstance(data, dict):
        return {k: scrub_decimals(v) for k, v in data.items()}
    if isinstance(data, decimal.Decimal):
        return int(data) if data % 1 == 0 else float(data)
    return data

# Sending HTTP response
def create_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(scrub_decimals(body)),
    }

# Parsing severity from AI response
def normalize_severity(value, error_type, log_message, root_cause):
    raw = (value or "").upper()
    if "HIGH" in raw:
        return "HIGH"
    if "MEDIUM" in raw:
        return "MEDIUM"
    if "LOW" in raw:
        return "LOW"
    if "WARNING" in raw:
        return "WARNING"
    return classify_severity(error_type, f"{root_cause} {log_message}")

# Sending metric to CloudWatch
def push_metric(metric_name, value):
    try:
        cloudwatch.put_metric_data(
            Namespace='AIOps-App',
            MetricData=[{'MetricName': metric_name, 'Value': value, 'Unit': 'Count'}]
        )
    except Exception:
        pass

# Parsing request body
def parse_body(event):
    try:
        return json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return {}

# Getting query parameter
def get_query_param(event, key, default=None):
    params = event.get("queryStringParameters") or {}
    return params.get(key, default)

# Fetching logs from URL
def get_logs():
    with urllib.request.urlopen(LOG_API) as response:
        return json.loads(response.read().decode())

# Tracking alert status in DynamoDB
def record_alert_status(incident_id, status, published_at=None, message_id=None, error=None):
    update = "SET alert_channel = :channel, alert_status = :status"
    values = {":channel": "SNS", ":status": status}

    if published_at:
        update += ", alert_published_at = :published_at"
        values[":published_at"] = published_at
    if message_id:
        update += ", alert_message_id = :message_id"
        values[":message_id"] = message_id
    if error:
        update += ", alert_error = :error"
        values[":error"] = error

    table.update_item(
        Key={"incident_id": incident_id},
        UpdateExpression=update,
        ExpressionAttributeValues=values
    )

# Clean up remediation text for email notification
def format_remediation(recommended_fix):
    if not recommended_fix:
        return "No specific remediation steps provided."

    if isinstance(recommended_fix, list):
        steps = []
        for i, step in enumerate(recommended_fix, 1):
            clean = str(step).strip().strip('[]').strip('"').strip("'")
            clean = re.sub(r'^\d+\.\s*', '', clean)
            clean = clean.replace('\\n', ' ').replace('\n', ' ')
            clean = ' '.join(clean.split())
            if clean and clean not in ['', '[]', '{}']:
                steps.append(f"{i}. {clean}")
        return '\n'.join(steps) if steps else "No valid remediation steps provided."

    if isinstance(recommended_fix, str):
        cleaned = recommended_fix.strip()
        if cleaned.startswith('[') and cleaned.endswith(']'):
            cleaned = cleaned[1:-1]
        cleaned = cleaned.strip('"').strip("'")
        cleaned = cleaned.replace('\\n', '\n')

        lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
        if lines:
            if any(re.match(r'^\d+\.', line) for line in lines):
                return '\n'.join(lines)
            return '\n'.join([f"{i+1}. {line}" for i, line in enumerate(lines)])
        return cleaned

    return str(recommended_fix)

# Sending email alert via SNS
def publish_incident_alert(incident):
    severity = incident.get("severity")
    if severity not in ["HIGH", "MEDIUM"]:
        return

    if not SNS_TOPIC_ARN:
        record_alert_status(incident["incident_id"], "CONFIG_MISSING")
        return

    try:
        if severity == "HIGH":
            emoji, urgency = "🚨🚨🚨", "CRITICAL - Immediate Action Required"
        else:
            emoji, urgency = "⚠️⚠️", "URGENT - Action Required Soon"

        remediation = format_remediation(incident.get('recommended_fix', ''))

        message = f"""
{emoji} AIOPS {severity} SEVERITY ALERT {emoji}
==================================================
Urgency: {urgency}
Severity: {incident.get('severity', 'UNKNOWN')}
Status: {incident.get('status', 'OPEN')}
Error Type: {incident.get('error_type', 'Unknown Error')}
Timestamp: {incident.get('timestamp', 'Unknown Time')}

==================================================
📌 ROOT CAUSE ANALYSIS:
--------------------------------------------------
{incident.get('root_cause', 'No root cause identified.')}

==================================================
🔧 RECOMMENDED FIX:
--------------------------------------------------
{remediation}

==================================================
System Log: {incident.get('log', 'N/A')}
Incident ID: {incident.get('incident_id', 'N/A')}
"""
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"AIOps Alert: {severity} - {incident.get('error_type')}",
            Message=message.strip()
        )
        record_alert_status(
            incident["incident_id"], "PUBLISHED",
            published_at=datetime.datetime.utcnow().isoformat(),
            message_id=response.get("MessageId")
        )
    except Exception as e:
        record_alert_status(incident["incident_id"], "FAILED", error=str(e))
        push_metric("AIFailures", 1)

# Calling Grok API to analyze log
def call_ai(log_message):
    prompt = f"""Analyze this AWS error log and return ONLY valid JSON.

Format:
{{
  "error_type": "short error category",
  "severity": "HIGH or MEDIUM or LOW",
  "root_cause": "brief explanation",
  "recommended_fix": "1. step one\\n2. step two\\n3. step three"
}}

Log: {log_message}"""

    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "grok-4.1-fast",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    response = requests.post(GROK_API_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    
    result = response.json()
    ai_response = result["choices"][0]["message"]["content"]
    
    # Clean markdown if present
    if ai_response.startswith('```json'):
        ai_response = ai_response[7:]
    if ai_response.startswith('```'):
        ai_response = ai_response[3:]
    if ai_response.endswith('```'):
        ai_response = ai_response[:-3]
    
    return json.loads(ai_response)

# Creating new incident
def create_incident():
    logs = get_logs()
    log_message = random.choice(logs)["log"]

    parsed = call_ai(log_message)

    severity = normalize_severity(
        parsed.get("severity"),
        parsed.get("error_type", "Unknown"),
        log_message,
        parsed.get("root_cause", "")
    )

    incident = build_incident(log_message, parsed, severity)
    incident["timestamp"] = datetime.datetime.utcnow().isoformat()
    incident["notes"] = []

    table.put_item(Item=incident)
    push_metric("TotalIncidents", 1)

    if severity in ["HIGH", "MEDIUM"]:
        if severity == "HIGH":
            push_metric("HighSeverityIncidents", 1)
        else:
            push_metric("MediumSeverityIncidents", 1)
        publish_incident_alert(incident)

    return incident

# Getting all incidents
def list_incidents():
    response = table.scan()
    items = response.get("Items", [])
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return items

# Updating incident status
def update_incident(body):
    incident_id = body.get("incident_id")
    status = (body.get("status") or "OPEN").strip().upper().replace(" ", "_")
    note = (body.get("note") or "").strip()

    if not incident_id:
        return create_response(400, {"message": "incident_id is required"})

    allowed = {"OPEN", "AWAITING_RESOLUTION", "RESOLVED"}
    if status not in allowed:
        return create_response(400, {"message": "Invalid status"})

    update = "SET #status = :status, updated_at = :updated_at"
    values = {":status": status, ":updated_at": datetime.datetime.utcnow().isoformat()}
    names = {"#status": "status"}

    if note:
        note_entry = f"{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} - {note}"
        update += ", notes = list_append(if_not_exists(notes, :empty), :note)"
        values[":note"] = [note_entry]
        values[":empty"] = []

    updated = table.update_item(
        Key={"incident_id": incident_id},
        UpdateExpression=update,
        ExpressionAttributeValues=values,
        ExpressionAttributeNames=names,
        ReturnValues="ALL_NEW"
    )

    if status == "RESOLVED":
        push_metric("ResolvedIncidents", 1)
        if S3_ARCHIVE_BUCKET:
            try:
                s3.put_object(
                    Bucket=S3_ARCHIVE_BUCKET,
                    Key=f"resolved_incidents/incident_{incident_id}.json",
                    Body=json.dumps(scrub_decimals(updated.get("Attributes", {})), indent=2),
                    ContentType="application/json"
                )
            except Exception:
                pass

    return create_response(200, {
        "message": "Incident updated",
        "incident": updated.get("Attributes", {})
    })

# Generating daily CSV report
def generate_daily_csv_report():
    if not S3_ARCHIVE_BUCKET:
        return create_response(500, {"message": "S3_ARCHIVE_BUCKET not configured"})

    items = list_incidents()
    resolved = [i for i in items if i.get("status") == "RESOLVED"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Incident ID", "Timestamp", "Severity", "Error Type", "Root Cause", "Recommended Fix", "Notes Count"])

    for item in resolved:
        fix = item.get("recommended_fix", "")
        if isinstance(fix, list):
            fix = ' | '.join(str(s) for s in fix)
        writer.writerow([
            item.get("incident_id", ""),
            item.get("timestamp", ""),
            item.get("severity", ""),
            item.get("error_type", ""),
            item.get("root_cause", ""),
            fix,
            len(item.get("notes", []))
        ])

    date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    key = f"reports/resolved_incidents_{date}.csv"

    try:
        s3.put_object(Bucket=S3_ARCHIVE_BUCKET, Key=key, Body=output.getvalue(), ContentType="text/csv")
        return create_response(200, {"message": f"CSV Report Generated at {key}"})
    except Exception as e:
        return create_response(500, {"message": str(e)})

# Main Lambda handler
def lambda_handler(event, _context):
    if event.get("source") == "eventbridge" or event.get("action") == "generate_report":
        return generate_daily_csv_report()

    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    if method == "OPTIONS":
        return create_response(200, {"message": "ok"})

    if method == "POST":
        body = parse_body(event)
        if body.get("action") == "delete":
            incident_id = body.get("incident_id")
            if not incident_id:
                return create_response(400, {"message": "incident_id is required"})
            try:
                table.delete_item(Key={"incident_id": incident_id})
                return create_response(200, {"message": "Incident deleted successfully"})
            except Exception as e:
                return create_response(500, {"message": f"Delete failed: {str(e)}"})
        return update_incident(body)

    if method == "DELETE":
        body = parse_body(event)
        incident_id = body.get("incident_id")
        if not incident_id:
            return create_response(400, {"message": "incident_id is required"})
        try:
            table.delete_item(Key={"incident_id": incident_id})
            return create_response(200, {"message": "Incident deleted successfully"})
        except Exception as e:
            return create_response(500, {"message": f"Delete failed: {str(e)}"})

    if method == "GET":
        action = (get_query_param(event, "action", "list") or "list").lower()
        if action == "generate":
            incident = create_incident()
            return create_response(200, {
                "message": "Incident generated",
                "incident": incident,
                "items": list_incidents()
            })
        return create_response(200, list_incidents())

    return create_response(405, {"message": "Method not allowed"})
    