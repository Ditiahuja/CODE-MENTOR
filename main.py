from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
from groq import Groq
import re
from dotenv import load_dotenv

load_dotenv()

# =========================
# CLEAN FUNCTION
# =========================
# def clean_text(text):
#     text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
#     text = text.replace("```python", "").replace("```", "")
#     text = text.replace("`", "")
#     return text.strip()


def clean_text(text):
    text = text.replace("```python", "")
    text = text.replace("```", "")
    text = text.replace("`", "")
    return text.strip()


app = FastAPI()

# =========================
#  CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
#  API KEY
# =========================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY not set")

client = Groq(api_key=GROQ_API_KEY)


class CodeInput(BaseModel):
    code: str


# =========================
#  RUN CODE
# =========================
@app.post("/run")
def run_code(data: CodeInput):
    try:
        result = subprocess.run(
            ["python", "-c", data.code], capture_output=True, text=True, timeout=5
        )

        output = result.stdout.strip()
        error = result.stderr.strip()
        explanation = ""

        if error:
            try:
                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {
                            "role": "system",
                            "content": """
Explain this Python error to a beginner.

Keep it under 100 words.

Format:

Error:
...

Why:
...

Fix:
...

Rules:
- No markdown
- No symbols like **
- Use very simple language
- Be short and clear

Format:
Error: <what happened> (two line gap)
Why: <why it happened> (two line gap)
Fix: <what to do>
""",
                        },
                        {
                            "role": "user",
                            "content": f"""
Code:

{data.code}

Error:

{error}

Fix this code.
""",
                        },
                    ],
                )

                explanation = response.choices[0].message.content or ""
                explanation = clean_text(explanation)

            except Exception as ai_error:
                print("❌ Explain ERROR:", ai_error)
                explanation = "AI explanation unavailable."

        return {"output": output, "error": error, "explanation": explanation}

    except subprocess.TimeoutExpired:
        return {
            "output": "",
            "error": "Execution timed out.",
            "explanation": "Your code may contain an infinite loop.",
        }

    except Exception as e:
        return {
            "output": "",
            "error": str(e),
            "explanation": "Unexpected error occurred.",
        }


# =========================
# FIX CODE
# =========================
@app.post("/fix")
def fix_code(data: CodeInput):
    try:
        print("🛠 Fixing code...")

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0,
            top_p=0.1,
            messages=[
                {
                    "role": "system",
                    "content": """
You are an expert Python debugger.

Fix the code and return ONLY the corrected Python code.

Rules:
- Return executable Python code only.
- No markdown.
- No explanations.
- No comments.
- Preserve the original intent.
- Make the smallest possible change.
- Avoid creating new functions unless necessary.
- Avoid importing libraries unless necessary.
- Prefer simple fixes.
- Output only the final corrected code.
""",
                },
                {"role": "user", "content": data.code},
            ],
        )

        fixed_code = response.choices[0].message.content or ""
        fixed_code = clean_text(fixed_code)

        return {"fixed_code": fixed_code}

    except Exception as e:
        print("❌ Fix ERROR:", e)

        return {"fixed_code": "Unable to generate fix."}
