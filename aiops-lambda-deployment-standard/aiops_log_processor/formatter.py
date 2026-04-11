import uuid


def build_incident(log, parsed, severity):
    return {
        "incident_id": str(uuid.uuid4()),
        "log": log,
        "error_type": parsed.get("error_type") or "Unknown",
        "severity": severity,
        "root_cause": parsed.get("root_cause") or "Not identified",
        "recommended_fix": parsed.get("recommended_fix") or "Manual investigation required",
        "status": "OPEN",
    }
