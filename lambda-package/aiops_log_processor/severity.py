def classify_severity(error_type, text):
    """
    Inspects the incident log payload for hardcoded critical keywords to programmatically
    determine the severity level. Defaults smoothly to MEDIUM if no critical infrastructure
    or basic timeout keywords are positively identified.
    """
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
