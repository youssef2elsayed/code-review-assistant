import os
import json
import re
from flask import Flask, render_template, request
from openai import OpenAI

# -----------------------------
# Flask Setup
# -----------------------------
app = Flask(__name__)

# -----------------------------
# OpenAI Client (secure key)
# -----------------------------
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# Language Detection (Heuristic)
# -----------------------------
def detect_language_heuristic(code: str) -> str:
    c = code.lower()

    # Strong C/C++ signals
    if "#include" in c or "std::" in c or "using namespace std" in c or "int main" in c:
        return "cpp"
    if re.search(r"\bcout\s*<<|\bcin\s*>>", code):
        return "cpp"

    # Strong JavaScript signals
    if "console.log" in c or "function " in c or "=>" in code or "let " in c or "const " in c:
        return "javascript"

    # Strong Python signals
    if re.search(r"^\s*def\s+\w+\(", code, flags=re.M) or "import " in c or "print(" in c:
        return "python"

    return "unknown"


def language_matches(selected: str, detected: str) -> bool:
    if detected == "unknown":
        return True  # don't block if unsure

    selected = (selected or "").lower()
    detected = (detected or "").lower()

    if selected in ("cpp", "c++") and detected == "cpp":
        return True
    if selected in ("javascript", "js") and detected == "javascript":
        return True
    if selected == "python" and detected == "python":
        return True

    return False


# -----------------------------
# AI Code Review Function
# Returns JSON object:
# {
#   complexity_score: int 1-10,
#   complexity_reason: str,
#   issues: [{ issue_type, severity, line, problem, why_it_matters, how_to_fix }]
# }
# -----------------------------
def ai_code_review(code: str, language: str, mode: str) -> str:
    if mode == "developer":
        style_rules = """
Explanation style: developer-focused.
- Use correct technical terms.
- Mention impact (bug risk, maintainability, performance).
- Keep it concise.
"""
    else:
        style_rules = """
Explanation style: beginner-friendly.
- Avoid jargon.
- Use short simple sentences.
- Explain clearly what is wrong and what to do.
"""

    prompt = f"""
You are a code reviewer.

{style_rules}

Analyse the following {language} code.

Return ONLY valid JSON (no extra text, no markdown) in this exact format:

{{
  "complexity_score": 1-10,
  "complexity_reason": "1-2 short sentences",
  "issues": [
    {{
      "issue_type": "Short category",
      "severity": "error|warning|info",
      "line": "line number or '-'",
      "problem": "What is wrong",
      "why_it_matters": "Why this is important",
      "how_to_fix": "How to fix it"
    }}
  ]
}}

Rules:
- complexity_score must be an integer 1–10.
- If no issues, return "issues": []
- Do NOT wrap JSON in ```.

Code:
{code}
""".strip()

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )

    return response.output_text


# -----------------------------
# Homepage Route
# -----------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        code="",
        issues=[],
        language="python",
        mode="beginner",
        complexity_score=None,
        complexity_reason=None
    )


# -----------------------------
# Analyse Route (FORM POST)
# -----------------------------
@app.route("/analyse", methods=["POST"])
def analyse():
    code = request.form.get("code", "").strip()
    language = request.form.get("language", "python").strip().lower()
    mode = "developer" if request.form.get("developer_mode") == "on" else "beginner"

    # Basic validation
    if not code:
        return render_template(
            "index.html",
            code="",
            language=language,
            mode=mode,
            complexity_score=None,
            complexity_reason=None,
            issues=[{
                "issue_type": "Input Error",
                "severity": "error",
                "line": "-",
                "problem": "No code was provided.",
                "why_it_matters": "The tool needs code to analyse.",
                "how_to_fix": "Paste some code into the text box and try again."
            }]
        )

    if not os.getenv("OPENAI_API_KEY"):
        return render_template(
            "index.html",
            code=code,
            language=language,
            mode=mode,
            complexity_score=None,
            complexity_reason=None,
            issues=[{
                "issue_type": "Config Error",
                "severity": "error",
                "line": "-",
                "problem": "Missing API key.",
                "why_it_matters": "Without an API key the AI cannot run.",
                "how_to_fix": "Set OPENAI_API_KEY in your terminal and restart the app."
            }]
        )

    # Language mismatch check
    detected = detect_language_heuristic(code)
    if not language_matches(language, detected):
        pretty = {"python": "Python", "cpp": "C++", "javascript": "JavaScript", "unknown": "Unknown"}
        return render_template(
            "index.html",
            code=code,
            language=language,
            mode=mode,
            complexity_score=None,
            complexity_reason=None,
            issues=[{
                "issue_type": "Language Mismatch",
                "severity": "error",
                "line": "-",
                "problem": "The selected language does not match the pasted code.",
                "why_it_matters": "Analysing code with the wrong language can produce incorrect feedback.",
                "how_to_fix": f"You selected {pretty.get(language, language)}, but this looks like {pretty.get(detected, detected)}. "
                              f"Change the dropdown or paste the correct code."
            }]
        )

    # Ask the AI
    try:
        feedback_text = ai_code_review(code, language, mode)

        # Parse JSON object
        try:
            payload = json.loads(feedback_text)
            if not isinstance(payload, dict):
                raise ValueError("AI did not return a JSON object")

            complexity_score = payload.get("complexity_score")
            complexity_reason = payload.get("complexity_reason")

            raw_issues = payload.get("issues", [])
            if not isinstance(raw_issues, list):
                raw_issues = []

            # Clean each issue
            cleaned_issues = []
            for item in raw_issues:
                if not isinstance(item, dict):
                    continue
                cleaned_issues.append({
                    "issue_type": item.get("issue_type", "Unknown"),
                    "severity": item.get("severity", "info"),
                    "line": item.get("line", "-"),
                    "problem": item.get("problem", ""),
                    "why_it_matters": item.get("why_it_matters", ""),
                    "how_to_fix": item.get("how_to_fix", "")
                })

            # Validate complexity score
            if not isinstance(complexity_score, int) or not (1 <= complexity_score <= 10):
                complexity_score = None
                if not isinstance(complexity_reason, str):
                    complexity_reason = None

            return render_template(
                "index.html",
                code=code,
                language=language,
                mode=mode,
                complexity_score=complexity_score,
                complexity_reason=complexity_reason,
                issues=cleaned_issues
            )

        except Exception:
            # JSON parse failed
            return render_template(
                "index.html",
                code=code,
                language=language,
                mode=mode,
                complexity_score=None,
                complexity_reason=None,
                issues=[{
                    "issue_type": "AI Parse Error",
                    "severity": "error",
                    "line": "-",
                    "problem": "The AI response could not be parsed as JSON.",
                    "why_it_matters": "The UI needs structured JSON to show separate issue cards.",
                    "how_to_fix": "Try again. If it persists, tighten the prompt or add JSON cleaning.",
                }]
            )

    except Exception as e:
        return render_template(
            "index.html",
            code=code,
            language=language,
            mode=mode,
            complexity_score=None,
            complexity_reason=None,
            issues=[{
                "issue_type": "System Error",
                "severity": "error",
                "line": "-",
                "problem": "The AI request failed.",
                "why_it_matters": "Without a successful AI response, no analysis can be shown.",
                "how_to_fix": f"Check your API key, billing, and internet connection. Error: {str(e)}"
            }]
        )


# -----------------------------
# Run Server
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5001)