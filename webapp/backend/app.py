"""
Flask backend for the Reddit Intelligence web app.
Provides a Gemini 2.5 Flash proxy for natural-language to SQL.
Reads GEMINI_API_KEY from the environment (load .env at repo root for local dev).
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

# Load .env from repo root when running locally (e.g. from webapp/backend/)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WEBAPP_ROOT = _REPO_ROOT / "webapp"
load_dotenv(_REPO_ROOT / ".env")

app = Flask(__name__, static_folder=str(_WEBAPP_ROOT), static_url_path="")

@app.route("/")
def index():
    """Serve the frontend."""
    return app.send_static_file("index.html")


@app.route("/semantic_layer.md")
def semantic_layer_doc():
    """Serve the semantic layer doc so the frontend schema link works when run from same origin."""
    path = _REPO_ROOT / "docs" / "semantic_layer.md"
    if not path.exists():
        return "", 404
    from flask import send_file
    return send_file(path, mimetype="text/markdown", as_attachment=False)


# CORS so static frontend (e.g. GitHub Pages) can call this backend
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def _get_semantic_layer_md() -> str:
    """Read canonical semantic layer from docs/semantic_layer.md."""
    path = _REPO_ROOT / "docs" / "semantic_layer.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _get_gemini_api_key() -> str:
    """Get Gemini API key from env or from secrets/gemini_api_key file."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    path = _REPO_ROOT / "secrets" / "gemini_api_key"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _call_gemini_nl_to_sql(question: str) -> str:
    """Call Gemini 2.5 Flash with semantic layer context; return generated SQL."""
    api_key = _get_gemini_api_key()
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) must be set, or place key in secrets/gemini_api_key"
        )

    import google.generativeai as genai

    genai.configure(api_key=api_key)

    semantic_md = _get_semantic_layer_md()
    system_instruction = (
        "You are a SQL expert for a DuckDB database. Use the following database schema and examples when writing SQL.\n\n"
        "Respond with only the SQL query, no markdown code fences, no explanation. One query only.\n\n"
        "---\n\n"
        + semantic_md
    )

    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=system_instruction,
    )
    response = model.generate_content(
        question,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
        ),
    )

    if not response or not response.text:
        raise ValueError("Empty response from Gemini")

    # Strip optional ```sql ... ``` wrapper
    text = response.text.strip()
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    return text


@app.route("/api/nl-to-sql", methods=["POST", "OPTIONS"])
def nl_to_sql():
    """Convert natural-language question to SQL using Gemini 2.5 Flash."""
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Missing or empty 'question' in JSON body"}), 400

    try:
        sql = _call_gemini_nl_to_sql(question)
        return jsonify({"sql": sql})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Gemini request failed: {e}"}), 500


@app.route("/api/run-sql", methods=["POST", "OPTIONS"])
def run_sql():
    """Execute read-only SQL against the DuckDB database. Only SELECT allowed."""
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(silent=True) or {}
    sql = (data.get("sql") or "").strip()
    if not sql:
        return jsonify({"error": "Missing or empty 'sql' in JSON body"}), 400

    # Allow only SELECT (read-only)
    normalized = sql.upper().strip()
    if not normalized.startswith("SELECT"):
        return jsonify({"error": "Only SELECT queries are allowed"}), 400

    db_path = os.environ.get("DUCKDB_PATH") or str(_REPO_ROOT / "data" / "reddit.duckdb")
    if not os.path.isfile(db_path):
        return jsonify({"error": f"Database not found at {db_path}"}), 503

    try:
        import duckdb
        conn = duckdb.connect(db_path, read_only=True)
        try:
            result = conn.execute(sql)
            rows = result.fetchall()
            columns = [d[0] for d in result.description] if result.description else []
            # Serialize rows for JSON (dates -> isoformat, rest as-is)
            def _serialize(c):
                if c is None:
                    return None
                if hasattr(c, "isoformat"):
                    return c.isoformat()
                return c

            serialized = [[_serialize(c) for c in row] for row in rows]
            return jsonify({"columns": columns, "rows": serialized})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": f"Query failed: {e}"}), 400


@app.route("/api/health", methods=["GET"])
def health():
    """Health check; confirms backend is up. Does not require GEMINI_API_KEY."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
