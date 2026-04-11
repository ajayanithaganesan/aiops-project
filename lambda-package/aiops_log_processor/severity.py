def classify_severity(error_type, text):
    text = text.lower()

    if "timeout" in text:
        return "HIGH"

    if "accessdenied" in text or "permission" in text:
        return "MEDIUM"

    if "connection refused" in text or "network" in text:
        return "HIGH"

    if "memory exceeded" in text:
        return "HIGH"

    if "warning" in text:
        return "LOW"

    return "MEDIUM"
