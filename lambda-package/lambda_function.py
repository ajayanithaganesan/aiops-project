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

# Configuration values and URL's
NGROK_URL = "https://doily-unenamelled-angelita.ngrok-free.dev/analyze"
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

# Sending metric to CloudWatch
def push_metric(metric_name, value):
    try:
        cloudwatch.put_metric_data(
            Namespace='AIOps-App',
            MetricData=[{'MetricName': metric_name, 'Value': value, 'Unit': 'Count'}]
        )
    except Exception:
        pass  # Don't crash if metrics fail

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

    # Handling list input
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

    # Handling string input
    if isinstance(recommended_fix, str):
        cleaned = recommended_fix.strip()
        if cleaned.startswith('[') and cleaned.endswith(']'):
            cleaned = cleaned[1:-1]
        cleaned = cleaned.strip('"').strip("'")
        cleaned = cleaned.replace('\\n', '\n')

        # Splitting into lines and clean
        lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
        if lines:
            # Checking if already numbered
            if any(re.match(r'^\d+\.', line) for line in lines):
                return '\n'.join(lines)
            # Adding numbers
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

# Calling local AI via Ngrok to analyze log
def call_ai(log_message):
    req = urllib.request.Request(
        NGROK_URL,
        data=json.dumps({"log": log_message}).encode(),
        headers={"Content-Type": "application/json"}
    )

    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = response.read().decode()
            try:
                result = json.loads(raw)
                if "analysis" in result:
                    return extract_from_text(result["analysis"])
                return result
            except json.JSONDecodeError:
                return extract_from_text(raw)
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")

    raise RuntimeError("AI failed after retries")

# Creating new incident
def create_incident():
    # Getting random log
    logs = get_logs()
    log_message = random.choice(logs)["log"]

    # Analyzing with AI
    try:
        parsed = call_ai(log_message)
    except Exception:
        parsed = {
            "error_type": "Timeout",
            "root_cause": "AI service not reachable",
            "recommended_fix": "Check ngrok connection",
        }

    # Using custom severity library to determine severity
    severity = classify_severity(
        parsed.get("error_type", "Unknown"),
        f"{parsed.get('root_cause', '')} {log_message}"
    )

    incident = build_incident(log_message, parsed, severity)
    incident["timestamp"] = datetime.datetime.utcnow().isoformat()
    incident["notes"] = []

    # Saving incident to DynamoDB
    table.put_item(Item=incident)
    push_metric("TotalIncidents", 1)

    # Sending alert for HIGH/MEDIUM severity incidents
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

    # Updating DynamoDB after incident status change
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

    # If incident is resolved, send metric and archive to S3 bucket
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

# Generating daily CSV report every 12 hours
def generate_daily_csv_report():
    if not S3_ARCHIVE_BUCKET:
        return create_response(500, {"message": "S3_ARCHIVE_BUCKET not configured"})

    items = list_incidents()
    resolved = [i for i in items if i.get("status") == "RESOLVED"]

    # Creating CSV
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

    # Uploading report to S3 bucket
    date = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    key = f"reports/resolved_incidents_{date}.csv"

    try:
        s3.put_object(Bucket=S3_ARCHIVE_BUCKET, Key=key, Body=output.getvalue(), ContentType="text/csv")
        return create_response(200, {"message": f"CSV Report Generated at {key}"})
    except Exception as e:
        return create_response(500, {"message": str(e)})

# Main Lambda handler
def lambda_handler(event, _context):
    # Handling EventBridge schedule for reports
    if event.get("source") == "eventbridge" or event.get("action") == "generate_report":
        return generate_daily_csv_report()

    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    # Handling CORS
    if method == "OPTIONS":
        return create_response(200, {"message": "ok"})

    # Handling POST requests
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

    # Handling DELETE requests
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

    # Handling GET requests
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