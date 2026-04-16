import re


def extract_from_text(text):
    """
    Reads the raw text response from the AI model and extracts the key fields — Error Type, Root Cause, 
    and Recommended Fix — using pattern matching, returning them as a structured dictionary.
    """
    def clean(value):
        # Removes markdown formatting and trims any extra whitespace from the extracted value
        return value.replace("**", "").strip()

    def find_block(start_label, end_label=None):
        # Extracts the text content found between two named section headers in the AI response
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
