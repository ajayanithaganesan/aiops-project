import re


def extract_from_text(text):
    """
    Parses unstructured raw text returned by the AI model into a mapped dictionary.
    Uses regex patterns to locate key infrastructure sections like Error Type,
    Root Cause, and Recommended Fixes based on standard model formatting variants.
    """
    def clean(value):
        # Strips out arbitrary markdown styling and whitespace edge artifacts
        return value.replace("**", "").strip()

    def find_block(start_label, end_label=None):
        # Dynamically grabs multiline string blocks between two boundary headers
        if end_label:
            pattern = rf"{start_label}\s*[:\-]?\s*(.*?)\s*{end_label}"
        else:
            pattern = rf"{start_label}\s*[:\-]?\s*(.*)"

        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        return clean(match.group(1)) if match else ""

    error_type_match = re.search(r"Error Type\s*[:\-]\s*(.*)", text, re.IGNORECASE)
    severity_match = re.search(r"Severity\s*[:\-]\s*(.*)", text, re.IGNORECASE)

    return {
        "error_type": clean(error_type_match.group(1)) if error_type_match else "",
        "severity": clean(severity_match.group(1)) if severity_match else "",
        "root_cause": find_block("Root Cause", "Recommended Fix"),
        "recommended_fix": find_block("Recommended Fix"),
    }
