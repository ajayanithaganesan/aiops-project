import uuid


def build_incident(log, parsed, severity):
    """
    Builds a structured incident record ready for DynamoDB storage.
    Generates a unique incident ID, fills in default values for any fields
    that AI did not return, and sets the initial status to OPEN.
    """
    return {
        "incident_id": str(uuid.uuid4()),
        "log": log,
        "error_type": parsed.get("error_type") or "Unknown",
        "severity": severity,
        "root_cause": parsed.get("root_cause") or "Not identified",
        "recommended_fix": parsed.get("recommended_fix") or "Manual investigation required",
        "status": "OPEN",
    }
