# 🚀 Automated Cold Job Outreach & Follow-up Pipeline

An end-to-end automated cold job application and follow-up engine designed to execute high-volume, personalized outreach campaigns. By leveraging semantic web search, contact details harvesting, verified B2B email search, and automated email threading, this codebase turns cold job hunting into an autonomous pipeline.

It is structured so that **any human user or AI coding agent** can clone the repository, add their credentials and CV, and manage their job application campaign.

---

## 🛠️ Architecture Overview

The pipeline consists of three core phases that can be run manually or triggered autonomously by an AI agent:

```
[Phase 1: DISCOVER] ──> [Phase 2: ENRICH] ──> [Phase 3: SEND & FOLLOW-UP]
  - Exa.ai Search          - Hunter.io API         - ReportLab PDF Letter Compiler
  - Directory Imports      - Prospeo API           - Secure SMTP SSL Client
                           - LinkedIn Matching     - Automated Follow-up Threading
```

*   **Phase 1: Discover:** Find companies based on custom search queries (e.g., target location, industry, funding stage, tech stack) using semantic web search, or import static target lists.
*   **Phase 2: Enrich:** Scrape domain contacts, identify key technical decision-makers (CTOs, Engineering Managers, HR heads) on LinkedIn, and retrieve their direct corporate emails.
*   **Phase 3: Send & Follow-up:** Dynamic-compile personalized cover letter PDFs tailored to the company's profile, attach your master CV, send via Gmail SMTP with anti-spam delays, and execute automatic in-thread follow-up check-ins 6 days later.

---

## 📂 Repository Structure

| File | Purpose |
| :--- | :--- |
| **`outreach_pipeline.py`** | Main orchestrator to run search, scrape, letter generation, and cold sends. |
| **`followup_pipeline.py`** | Follow-up manager to check candidate dates, apply exclusions, and send in-thread check-ins. |
| **`email_sender.py`** | Secure SMTP client with attachment routing. |
| **`cover_letter_generator.py`** | Dynamic PDF compiler using ReportLab styles. |
| **`config.py`** | Zero-dependency environment variable loader. |
| **`apify_scraper.py`** | Apify Actor interface for crawling domain contact pages. |
| **`exa_search.py`** | Exa API wrapper for semantic queries. |
| **`outreach_queue.csv`** | Central SQLite-like tracking database of target companies and statuses. |
| **`outreach_log.csv`** | History of successfully executed sends and timestamps. |
| **`app.py`** | Local Flask **web control panel** that drives the whole pipeline from a browser. |
| **`ui/`** | Front-end for the control panel (`index.html`, `style.css`, `app.js`). |
| **`start_ui.ps1` / `start_ui.bat`** | One-step launchers that set up the venv and open the control panel. |

---

## 🖥️ Easiest Way to Run It: The Control Panel UI

If you'd rather not touch the command line, a built-in **web control panel** drives the entire pipeline from your browser — review the queue, run each phase with one click and watch live logs, browse generated cover letters, read the send history, and manage credentials.

### ▶️ How to run it locally

**Option A — the one-click launcher (recommended):**

Just **double-click `start_ui.bat`** in the project folder (or right-click `start_ui.ps1` → *Run with PowerShell*).
It creates the virtual environment, installs the dependencies, and opens the panel for you. Nothing else to type.

**Option B — from a terminal.** Open PowerShell in the project folder and run:

```powershell
# 1. Go to the project folder
cd "C:\Users\Emmanuel Jesse\Downloads\Job_Seeker\job-outreach-pipeline"

# 2. First time only: create the venv and install dependencies
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Start the control panel (every time)
.\.venv\Scripts\python.exe app.py
```

Then open **http://127.0.0.1:5000** in your browser (it also opens automatically).
Press **Ctrl + C** in the terminal to stop the server.

> Already set up? The only command you need from then on is the last one:
> `.\.venv\Scripts\python.exe app.py`
>
> Port 5000 busy? Run `$env:PORT=5050; .\.venv\Scripts\python.exe app.py` and use that port.

**What's inside the panel:**

| Page | What it does |
| :--- | :--- |
| **Dashboard** | Live queue counts, a setup checklist, and the pipeline flow at a glance. |
| **Run Pipeline** | One-click **Search → Scrape → Generate → Send**, each with a live console. |
| **Queue** | Edit any company inline, add companies, and bulk-**Approve** everyone with an email. |
| **Follow-ups** | Preview who's due for a 6-day check-in, then send live (max 10). |
| **Letters** | Open and review every generated cover-letter PDF before sending. |
| **Send Log** | Full history of every email the pipeline attempted. |
| **Settings** | Enter your API keys, Gmail credentials, and CV filename — saved locally to `.env`. |

> First run? Open **Settings** and fill in your keys, then add your CV PDF (see step 3 below) — the Dashboard checklist turns green as each piece is in place. Sending always asks for confirmation first.

The command-line workflow below still works exactly as before for anyone who prefers it.

---

## 🚀 Setup Instructions

Follow these steps to get your own job outreach campaign running:

### 1. Clone & Install Dependencies
Make sure you have Python 3.10+ installed. From the repository directory, create an isolated environment and install the dependencies:
```bash
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and run the pipeline with `.\.venv\Scripts\python.exe`.

### 2. Configure Credentials
Copy the example environment file:
