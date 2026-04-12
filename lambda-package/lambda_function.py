import datetime
import json
import os
import random
import urllib.request
import csv
import io

import boto3
from aiops_log_processor.formatter import build_incident
from aiops_log_processor.parser import extract_from_text
from aiops_log_processor.severity import classify_severity


dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")
s3 = boto3.client("s3")
table = dynamodb.Table("aiops-incidents")
cloudwatch = boto3.client('cloudwatch')

NGROK_URL = "https://doily-unenamelled-angelita.ngrok-free.dev/analyze"
LOG_API = "https://raw.githubusercontent.com/ajayanithaganesan/aiops-log-data/main/logs.json"
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "").strip()
S3_ARCHIVE_BUCKET = os.environ.get("S3_ARCHIVE_BUCKET", "").strip()

RESPONSE_HEADERS = {
    "Content-Type": "application/json",
}


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": RESPONSE_HEADERS,
        "body": json.dumps(body),
    }
def normalize_severity(value, error_type, log_message, root_cause):
    raw_severity = (value or "").upper()

    if "HIGH" in raw_severity:
        return "HIGH"
    if "MEDIUM" in raw_severity:
        return "MEDIUM"
    if "LOW" in raw_severity:
        return "LOW"
    if "WARNING" in raw_severity:
        return "WARNING"
    return classify_severity(error_type, f"{root_cause} {log_message}")

def push_metric(metric_name, value):
    try:
        cloudwatch.put_metric_data(
            Namespace='AIOps-App',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': 'Count'
                }
            ]
        )
    except Exception as e:
        print("CloudWatch Metric Error:", str(e))

def parse_body(event):
    raw_body = event.get("body") or "{}"
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return {}


def get_query_param(event, key, default=None):
    params = event.get("queryStringParameters") or {}
    return params.get(key, default)


def get_logs():
    with urllib.request.urlopen(LOG_API) as response_handle:
        return json.loads(response_handle.read().decode())


def record_alert_status(incident_id, status, published_at=None, message_id=None, error=None):
    update_expression = "SET alert_channel = :channel, alert_status = :status"
    expression_attribute_values = {
        ":channel": "SNS",
        ":status": status,
    }

    if published_at:
        update_expression += ", alert_published_at = :published_at"
        expression_attribute_values[":published_at"] = published_at

    if message_id:
        update_expression += ", alert_message_id = :message_id"
        expression_attribute_values[":message_id"] = message_id

    if error:
        update_expression += ", alert_error = :error"
        expression_attribute_values[":error"] = error

    table.update_item(
        Key={"incident_id": incident_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
    )


def publish_incident_alert(incident):
    if incident.get("severity") != "HIGH":
        return

    if not SNS_TOPIC_ARN:
        incident["alert_channel"] = "SNS"
        incident["alert_status"] = "CONFIG_MISSING"
        record_alert_status(incident["incident_id"], "CONFIG_MISSING")
        return

    message = {
        "incident_id": incident.get("incident_id"),
        "severity": incident.get("severity"),
        "status": incident.get("status"),
        "error_type": incident.get("error_type"),
        "root_cause": incident.get("root_cause"),
        "recommended_fix": incident.get("recommended_fix"),
        "timestamp": incident.get("timestamp"),
    }

    try:
        publish_response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"AIOps HIGH Incident: {incident.get('error_type', 'Unknown')}",
            Message=json.dumps(message, indent=2),
        )
        published_at = datetime.datetime.utcnow().isoformat()
        incident["alert_channel"] = "SNS"
        incident["alert_status"] = "PUBLISHED"
        incident["alert_published_at"] = published_at
        incident["alert_message_id"] = publish_response.get("MessageId")
        record_alert_status(
            incident["incident_id"],
            "PUBLISHED",
            published_at=published_at,
            message_id=publish_response.get("MessageId"),
        )
    except Exception as exc:
        incident["alert_channel"] = "SNS"
        incident["alert_status"] = "FAILED"
        incident["alert_error"] = str(exc)
        record_alert_status(incident["incident_id"], "FAILED", error=str(exc))
        push_metric("AIFailures", 1)


def call_ai(log_message):
    req = urllib.request.Request(
        NGROK_URL,
        data=json.dumps({"log": log_message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    for attempt in range(2):  # retry once
        try:
            with urllib.request.urlopen(req, timeout=15) as response_handle:
                raw_response = response_handle.read().decode("utf-8")

            try:
                ai_result = json.loads(raw_response)
                if "analysis" in ai_result:
                    return extract_from_text(ai_result["analysis"])
                return ai_result
            except:
                return extract_from_text(raw_response)

        except Exception as e:
            print(f"Attempt {attempt+1} failed:", str(e))

    raise Exception("AI failed after retries")


def create_incident():
    logs = get_logs()
    log_message = random.choice(logs)["log"]

    try:
        parsed = call_ai(log_message)
    except Exception as exc:
        print("AI ERROR:", str(exc))
        parsed = {
            "error_type": "Timeout",
            "severity": "HIGH",
            "root_cause": "AI service not reachable",
            "recommended_fix": "Check local AI / ngrok connection",
        }

    error_type = parsed.get("error_type") or "Unknown"
    root_cause = parsed.get("root_cause") or "Not identified"
    severity = normalize_severity(
        parsed.get("severity"), error_type, log_message, root_cause
    )

    incident = build_incident(log_message, parsed, severity)
    incident["timestamp"] = datetime.datetime.utcnow().isoformat()
    incident["notes"] = []

    table.put_item(Item=incident)
    # 🔥 CloudWatch Metrics
    push_metric("TotalIncidents", 1)

    if severity == "HIGH":
        push_metric("HighSeverityIncidents", 1)
        publish_incident_alert(incident)
    return incident


def list_incidents():
    db_response = table.scan()
    items = db_response.get("Items", [])
    items.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return items

def count_resolved_incidents():
    try:
        response = table.scan()
        items = response.get("Items", [])

        resolved_count = sum(1 for item in items if item.get("status") == "RESOLVED")

        return resolved_count

    except Exception as e:
        print("Error counting resolved incidents:", str(e))
        return 0


def update_incident(body):
    incident_id = body.get("incident_id")
    status = (body.get("status") or "OPEN").strip().upper().replace(" ", "_")
    note = (body.get("note") or "").strip()

    if not incident_id:
        return response(400, {"message": "incident_id is required"})

    allowed_statuses = {"OPEN", "AWAITING_RESOLUTION", "RESOLVED"}
    if status not in allowed_statuses:
        return response(400, {"message": "Invalid status"})

    update_expression = "SET #status = :status, updated_at = :updated_at"
    expression_attribute_values = {
        ":status": status,
        ":updated_at": datetime.datetime.utcnow().isoformat(),
    }
    expression_attribute_names = {"#status": "status"}

    if note:
        note_entry = (
            f"{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} - {note}"
        )
        update_expression += ", notes = list_append(if_not_exists(notes, :empty), :note)"
        expression_attribute_values[":note"] = [note_entry]
        expression_attribute_values[":empty"] = []

    updated = table.update_item(
        Key={"incident_id": incident_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
        ExpressionAttributeNames=expression_attribute_names,
        ReturnValues="ALL_NEW",
    )

    # 🔥 CloudWatch Metric for Resolved Incidents
    if status == "RESOLVED":
        total_resolved = count_resolved_incidents()
        push_metric("ResolvedIncidents", total_resolved)

        # 🗄️ S3 Archiving
        if S3_ARCHIVE_BUCKET:
            try:
                incident_data = updated.get("Attributes", {})
                s3.put_object(
                    Bucket=S3_ARCHIVE_BUCKET,
                    Key=f"resolved_incidents/incident_{incident_id}.json",
                    Body=json.dumps(incident_data, default=str, indent=2),
                    ContentType="application/json"
                )
            except Exception as e:
                print("S3 Export Error:", str(e))

    return response(
        200,
        {"message": "Incident updated", "incident": updated.get("Attributes", {})},
    )


def generate_daily_csv_report():
    if not S3_ARCHIVE_BUCKET:
        return response(500, {"message": "S3_ARCHIVE_BUCKET not configured"})

    items = list_incidents()
    resolved_items = [item for item in items if item.get("status") == "RESOLVED"]

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    
    # Headers
    writer.writerow(["Incident ID", "Timestamp", "Severity", "Error Type", "Root Cause", "Recommended Fix", "Notes Count"])
    
    for item in resolved_items:
        writer.writerow([
            item.get("incident_id", ""),
            item.get("timestamp", ""),
            item.get("severity", ""),
            item.get("error_type", ""),
            item.get("root_cause", ""),
            item.get("recommended_fix", ""),
            len(item.get("notes", []))
        ])
    
    date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    s3_key = f"reports/resolved_incidents_{date_str}.csv"
    
    try:
        s3.put_object(
            Bucket=S3_ARCHIVE_BUCKET,
            Key=s3_key,
            Body=csv_buffer.getvalue(),
            ContentType="text/csv"
        )
        return response(200, {"message": f"CSV Report Generated at {s3_key}"})
    except Exception as e:
        print("S3 Report Error:", str(e))
        return response(500, {"message": str(e)})

def lambda_handler(event, context):
    # EventBridge Scheduler Catch
    if event.get("source") == "eventbridge" or event.get("action") == "generate_report":
        return generate_daily_csv_report()

    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    if method == "OPTIONS":
        return response(200, {"message": "ok"})

    if method == "POST":
        return update_incident(parse_body(event))

    if method == "GET":
        action = (get_query_param(event, "action", "list") or "list").lower()
        if action == "generate":
            incident = create_incident()
            return response(
                200,
                {
                    "message": "Incident generated",
                    "incident": incident,
                    "items": list_incidents(),
                },
            )
        return response(200, list_incidents())

    return response(405, {"message": "Method not allowed"})
