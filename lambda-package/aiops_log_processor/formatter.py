import uuid


def build_incident(log, parsed, severity):
    """
    Constructs a standardized incident dictionary blueprint for DynamoDB storage.
    Automatically assigns a uniquely generated incident ID, applies default fallbacks
    if the AI parser missed structured fields, and initializes the ticket as OPEN.
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
