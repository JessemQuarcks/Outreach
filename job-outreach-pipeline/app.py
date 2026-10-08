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

