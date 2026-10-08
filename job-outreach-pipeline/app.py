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

