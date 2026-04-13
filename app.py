from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
import requests
import json
import re

app = FastAPI()

# Ollama local endpoint
OLLAMA_URL = "http://localhost:11434/api/generate"
LAMBDA_BASE_URL = "https://5g6wjqdenakuiatlv2jv2nbdty0iqxub.lambda-url.us-east-1.on.aws/"
INDEX_HTML_PATH = "index.html"


@app.get("/")
async def serve_dashboard():
    return FileResponse(INDEX_HTML_PATH)


@app.get("/api/incidents")
async def list_incidents(action: str | None = None):
    target_url = LAMBDA_BASE_URL
    params = {}

    if action:
        params["action"] = action

    try:
        response = requests.get(target_url, params=params, timeout=30)
        return JSONResponse(status_code=response.status_code, content=response.json())
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"message": f"Unable to reach Lambda backend: {str(e)}"},
        )


@app.post("/api/incidents")
async def update_incident(request: Request):
    try:
        payload = await request.json()
        response = requests.post(LAMBDA_BASE_URL, json=payload, timeout=30)
        return JSONResponse(status_code=response.status_code, content=response.json())
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"message": f"Unable to reach Lambda backend: {str(e)}"},
        )


@app.delete("/api/incidents")
async def delete_incident(request: Request):
    try:
        payload = await request.json()
        response = requests.delete(LAMBDA_BASE_URL, json=payload, timeout=30)
        return JSONResponse(status_code=response.status_code, content=response.json())
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"message": f"Unable to reach Lambda backend: {str(e)}"},
        )


@app.post("/analyze")
async def analyze_log(data: dict):
    log = data.get("log", "")

    # Updated prompt to request LIST format
    prompt = f"""
You are an AWS Cloud Incident Analyzer.

Analyze the given AWS log and return ONLY valid JSON.

Rules:
- Do NOT include explanations outside JSON
- Do NOT use markdown
- Keep the root_cause specific
- Provide 3 distinct, detailed, and actionable resolutions in the recommended_fix field as a LIST of strings
- Do NOT include severity in the response

Format:
{{
  "error_type": "",
  "root_cause": "",
  "recommended_fix": ["1. First step", "2. Second step", "3. Third step"]
}}

Log:
{log}
"""

    try:
        # Call Ollama
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "phi4-mini:latest",
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )

        raw_output = response.json().get("response", "")

        # Clean markdown
        raw_output = re.sub(r'```json\s*', '', raw_output)
        raw_output = re.sub(r'```\s*', '', raw_output)
        
        # Extract JSON safely
        start = raw_output.find("{")
        end = raw_output.rfind("}") + 1
        
        if start != -1 and end != 0:
            json_str = raw_output[start:end]
            parsed = json.loads(json_str)
        else:
            raise ValueError("No JSON found")

        # Ensure recommended_fix is a list
        if "recommended_fix" in parsed:
            if isinstance(parsed["recommended_fix"], str):
                # Convert string with \n to list
                parsed["recommended_fix"] = [step.strip() for step in parsed["recommended_fix"].split('\n') if step.strip()]
            elif not isinstance(parsed["recommended_fix"], list):
                parsed["recommended_fix"] = [str(parsed["recommended_fix"])]
        else:
            parsed["recommended_fix"] = ["Manual investigation required"]

    except Exception as e:
        # Fallback if parsing fails
        parsed = {
            "error_type": "Unknown",
            "root_cause": str(e),
            "recommended_fix": ["1. Check logs manually", "2. Investigate error", "3. Contact support"]
        }

    return parsed