"""
Job Outreach Pipeline — Local Web Control Panel
================================================

A single-file Flask app that wraps the existing CLI pipeline so the whole
campaign can be operated from a browser: review the queue, run each phase
(search / scrape / generate / send / follow-up) with live logs, browse the
generated cover letters, read the send log, and manage credentials.

Run it with:  python app.py   (or use start_ui.ps1 / start_ui.bat)
It opens http://127.0.0.1:5000 in your browser.

Nothing in the original pipeline is changed — this only calls into it.
"""

import os
import sys
import csv
import io
import json
import time
import threading
import traceback
import webbrowser
from datetime import datetime

# Always operate from the project directory so the pipeline's relative
# file paths (outreach_queue.csv, generated_letters/, .env ...) resolve.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from flask import Flask, jsonify, request, send_from_directory, abort, Response
except ImportError:
    sys.stderr.write(
        "\n[!] Flask is not installed.\n"
        "    Install it with:  python -m pip install flask\n"
        "    (or just run start_ui.ps1 / start_ui.bat which installs it for you)\n\n"
    )
    raise

# Import the existing pipeline modules. These are lazy about API keys
# (services are only constructed when a job actually runs), so importing
# here is safe even before credentials are configured.
import config as config_module
import outreach_pipeline as pipeline
import followup_pipeline as followup

app = Flask(__name__, static_folder=None)

QUEUE_FILE = pipeline.QUEUE_FILE
LOG_FILE = pipeline.LOG_FILE
LETTERS_DIR = pipeline.LETTERS_DIR
ENV_FILE = ".env"

QUEUE_FIELDS = [
    "company_name", "website", "email", "company_type",
    "recipient_name", "company_address", "status",
    "date_added", "date_sent",
]

STATUS_VALUES = ["Pending", "Approved", "Sent", "Failed", "Skipped", "Followup-Sent"]

ENV_KEYS = [
    "EXA_API_KEY", "APIFY_API_TOKEN", "HUNTER_API_KEY", "PROSPEO_API_KEY",
    "SENDER_EMAIL", "GMAIL_APP_PASSWORD", "CV_PATH",
]
SECRET_KEYS = {"EXA_API_KEY", "APIFY_API_TOKEN", "HUNTER_API_KEY",
               "PROSPEO_API_KEY", "GMAIL_APP_PASSWORD"}


# --------------------------------------------------------------------------
# Background job runner (one job at a time, with captured live logs)
# --------------------------------------------------------------------------
class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.name = None
        self.status = "idle"      # idle | running | done | error
        self.log = ""
        self.started = None
        self.finished = None
        self.thread = None

    def is_running(self):
        return self.status == "running"


JOB = Job()


class _LogWriter(io.TextIOBase):
    """File-like object that appends everything printed into the job log."""

    def write(self, s):
        if s:
            with JOB.lock:
                JOB.log += s
        return len(s)

    def flush(self):
        pass


def run_job(name, target):
    """Start `target()` in a background thread, capturing its stdout/stderr."""
    if JOB.is_running():
        return False

    with JOB.lock:
        JOB.name = name
        JOB.status = "running"
        JOB.log = ""
        JOB.started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        JOB.finished = None

    def _wrapped():
        writer = _LogWriter()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = writer
        try:
            target()
            status = "done"
        except SystemExit as e:  # some pipeline paths call sys.exit on bad config
            print(f"\n[!] Stopped: {e}")
            status = "error"
        except Exception:
            print("\n[!] The job failed with an error:\n")
            print(traceback.format_exc())
            status = "error"
        finally:
            sys.stdout, sys.stderr = old_out, old_err
            with JOB.lock:
                JOB.status = status
                JOB.finished = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    JOB.thread = threading.Thread(target=_wrapped, daemon=True)
    JOB.thread.start()
    return True


# --------------------------------------------------------------------------
# Config / credentials helpers
# --------------------------------------------------------------------------
def read_env():
    values = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values


def write_env(new_values):
    """Merge new values into .env, preserving existing keys/comments order."""
    existing = read_env()
    merged = dict(existing)
    for k, v in new_values.items():
        merged[k] = v

    lines = [
        "# API Keys for Lead Discovery & Enrichment",
        f"EXA_API_KEY={merged.get('EXA_API_KEY', '')}",
        f"APIFY_API_TOKEN={merged.get('APIFY_API_TOKEN', '')}",
        f"HUNTER_API_KEY={merged.get('HUNTER_API_KEY', '')}",
        f"PROSPEO_API_KEY={merged.get('PROSPEO_API_KEY', '')}",
        "",
        "# Sender Email Settings",
        f"SENDER_EMAIL={merged.get('SENDER_EMAIL', '')}",
        f"GMAIL_APP_PASSWORD={merged.get('GMAIL_APP_PASSWORD', '')}",
    ]
    if merged.get("CV_PATH"):
        lines += ["", "# Resume / CV file used for attachments", f"CV_PATH={merged['CV_PATH']}"]

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    reload_config()


def reload_config():
    """Re-read .env into the pipeline's config + environment, and reset any
    cached service clients so new credentials take effect immediately."""
    values = read_env()
    # Refresh the shared Config object used across the pipeline modules.
    config_module.config.env = dict(values)
    for k, v in values.items():
        os.environ[k] = v
    # Reset cached service singletons so they re-init with fresh keys.
    pipeline.exa = None
    pipeline.apify = None
    pipeline.sender = None
    # Allow a custom CV path to flow into both pipelines.
    cv = values.get("CV_PATH")
    if cv:
        pipeline.CV_PATH = cv
        followup.CV_PATH = cv


def cv_path():
    return getattr(pipeline, "CV_PATH", "")


# --------------------------------------------------------------------------
# Queue helpers
# --------------------------------------------------------------------------
def load_queue():
    return pipeline.load_queue()


def save_queue(queue):
    pipeline.save_queue(queue)


def compute_stats(queue):
    stats = {s: 0 for s in STATUS_VALUES}
    no_email = 0
    for r in queue:
        st = r.get("status", "Pending")
        stats[st] = stats.get(st, 0) + 1
        if not r.get("email"):
            no_email += 1
    return stats, no_email


# --------------------------------------------------------------------------
# API: status / dashboard
# --------------------------------------------------------------------------
@app.route("/api/status")
def api_status():
    queue = load_queue()
    stats, no_email = compute_stats(queue)
    env = read_env()

    def is_set(key):
        v = env.get(key, "")
        placeholders = ("your_", "xxxx", "@gmail.com") if key == "SENDER_EMAIL" else ("your_", "xxxx")
        if not v:
            return False
        low = v.lower()
        if key == "SENDER_EMAIL":
            return "your_gmail_address_here" not in low
        return not any(low.startswith(p) or p in low for p in ("your_", "xxxx"))

    credentials = {k: is_set(k) for k in ENV_KEYS if k != "CV_PATH"}

    letters = []
    if os.path.isdir(LETTERS_DIR):
        letters = [f for f in os.listdir(LETTERS_DIR) if f.lower().endswith(".pdf")]

    cv = cv_path()
    return jsonify({
        "total": len(queue),
        "stats": stats,
        "no_email": no_email,
        "credentials": credentials,
        "ready_to_send": stats.get("Approved", 0),
        "letters_count": len(letters),
        "cv_path": cv,
        "cv_exists": bool(cv) and os.path.exists(cv),
        "job": job_payload(),
    })


# --------------------------------------------------------------------------
# API: queue CRUD
# --------------------------------------------------------------------------
@app.route("/api/queue")
def api_queue():
    queue = load_queue()
    rows = []
    for i, r in enumerate(queue):
        row = {f: r.get(f, "") for f in QUEUE_FIELDS}
        row["_i"] = i
        rows.append(row)
    return jsonify({"rows": rows, "fields": QUEUE_FIELDS, "statuses": STATUS_VALUES})


@app.route("/api/queue/add", methods=["POST"])
def api_queue_add():
    data = request.get_json(force=True) or {}
    name = (data.get("company_name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Company name is required."}), 400
    ok = pipeline.add_to_queue(
        company_name=name,
        website=(data.get("website") or "").strip(),
        email=(data.get("email") or "").strip(),
        company_type=(data.get("company_type") or "general_startup").strip(),
        recipient=(data.get("recipient_name") or "The Recruiting and Technology Team").strip(),
        address=(data.get("company_address") or "Accra, Ghana").strip(),
    )
    if not ok:
        return jsonify({"ok": False, "error": "A company with that name or website already exists."}), 409
    return jsonify({"ok": True})


@app.route("/api/queue/update", methods=["POST"])
def api_queue_update():
    data = request.get_json(force=True) or {}
    idx = data.get("_i")
    queue = load_queue()
    if idx is None or not (0 <= idx < len(queue)):
        return jsonify({"ok": False, "error": "Row not found."}), 404
    row = queue[idx]
    for f in QUEUE_FIELDS:
        if f in data:
            row[f] = (data[f] or "").strip()
    save_queue(queue)
    return jsonify({"ok": True})


@app.route("/api/queue/delete", methods=["POST"])
def api_queue_delete():
    data = request.get_json(force=True) or {}
    idx = data.get("_i")
    queue = load_queue()
    if idx is None or not (0 <= idx < len(queue)):
        return jsonify({"ok": False, "error": "Row not found."}), 404
    queue.pop(idx)
    save_queue(queue)
    return jsonify({"ok": True})


@app.route("/api/queue/bulk", methods=["POST"])
def api_queue_bulk():
    """Bulk set a status. Optionally scope to rows currently in `from_status`
    and/or require a non-empty email (used for 'approve all scraped')."""
    data = request.get_json(force=True) or {}
    to_status = data.get("to_status")
    from_status = data.get("from_status")       # optional filter
    require_email = bool(data.get("require_email"))
    indices = data.get("indices")               # optional explicit selection
    if to_status not in STATUS_VALUES:
        return jsonify({"ok": False, "error": "Invalid status."}), 400

    queue = load_queue()
    changed = 0
    for i, r in enumerate(queue):
        if indices is not None and i not in indices:
            continue
        if from_status and r.get("status") != from_status:
            continue
        if require_email and not r.get("email"):
            continue
        if r.get("status") != to_status:
            r["status"] = to_status
            changed += 1
    save_queue(queue)
    return jsonify({"ok": True, "changed": changed})


# --------------------------------------------------------------------------
# API: credentials / settings
# --------------------------------------------------------------------------
@app.route("/api/config", methods=["GET"])
def api_config_get():
    env = read_env()
    out = {}
    for k in ENV_KEYS:
        v = env.get(k, "")
        if k in SECRET_KEYS:
            # Never send secrets back to the browser; just say whether it's set.
            out[k] = {"set": bool(v) and not v.lower().startswith(("your_", "xxxx")), "secret": True}
        else:
            out[k] = {"value": v, "secret": False}
    return jsonify({"config": out, "cv_exists": bool(cv_path()) and os.path.exists(cv_path())})


@app.route("/api/config", methods=["POST"])
def api_config_set():
    data = request.get_json(force=True) or {}
    new_values = {}
    for k in ENV_KEYS:
        if k in data:
            val = (data[k] or "").strip()
            # For secrets, an empty submission means "leave unchanged".
            if k in SECRET_KEYS and val == "":
                continue
            new_values[k] = val
    write_env(new_values)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# API: generated letters
# --------------------------------------------------------------------------
@app.route("/api/letters")
def api_letters():
    items = []
    if os.path.isdir(LETTERS_DIR):
        for f in sorted(os.listdir(LETTERS_DIR)):
            if f.lower().endswith(".pdf"):
                full = os.path.join(LETTERS_DIR, f)
                items.append({
                    "name": f,
                    "size_kb": round(os.path.getsize(full) / 1024, 1),
                    "modified": datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M"),
                })
    return jsonify({"letters": items})


@app.route("/api/letters/<path:filename>")
def api_letter_file(filename):
    if not os.path.isdir(LETTERS_DIR):
        abort(404)
    return send_from_directory(LETTERS_DIR, filename, as_attachment=False)


# --------------------------------------------------------------------------
# API: send log history
# --------------------------------------------------------------------------
@app.route("/api/logs")
def api_logs():
    rows = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    rows.reverse()  # newest first
    return jsonify({"rows": rows})


# --------------------------------------------------------------------------
# API: follow-up preview (dry-run candidates, no send)
# --------------------------------------------------------------------------
@app.route("/api/followups/preview")
def api_followups_preview():
    try:
        candidates = followup.get_followup_candidates()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    out = [{
        "company_name": c.get("company_name", ""),
        "email": c.get("email", ""),
        "date_sent": c.get("date_sent", ""),
    } for c in candidates]
    return jsonify({"ok": True, "candidates": out, "count": len(out)})

