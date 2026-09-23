# 🤖 F.R.I.D.A.Y. — Autonomous Browser Copilot

**FRIDAY** is an autonomous web automation AI agent designed to execute real-world browser chores from natural language instructions. Powered by **Playwright**, native **Brave Browser** integration, and text-based DOM reasoning (compatible with any Gemini / custom API instance ).

---

## ✨ Key Capabilities

- **🦁 Native Brave Browser Integration**: Runs directly with your installed Brave browser. Connects to your real, daily **Work** profile with all your saved passwords, cookies, and logged-in accounts.
- **📝 Text-Based DOM Perception**: Operates completely in **Text-Only Mode** — no multimodal vision tokens required. Compatible with any text model, reading page headings, text excerpts, and structured interactive tables.
- **🎯 Self-Healing Interaction Loop**: Uses Set-of-Marks (SoM) element labeling (`[1]`, `[2]`, `[3]`, ...). If single-page apps (SPAs) shift or re-render during automation, FRIDAY automatically recovers using viewport coordinate fallbacks.
- **⚡ Real Account Access (`connect-brave`)**: Connects directly to your live open Brave browser over Chrome DevTools Protocol (`--remote-debugging-port=9222`), bypassing Windows profile locks.
- **📥 Chores & Workflows**: Handles multi-step form submissions, data scraping into JSON/CSV, and file downloads directly to `downloads/`.

---

## 🏗️ Architecture

```
                    ┌──────────────────────────────┐
                    │     User Natural Instruction │
                    │ ("Check notifications on GH")│
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │     Perception & DOM State   │
                    │  - Injects badge IDs ([1]..) │
                    │  - Extracts headings & text  │
                    │  - Builds interactive table  │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    F.R.I.D.A.Y. Brain (LLM)  │
                    │  (Reasoning & Next Step JSON)│
                    │  Endpoint: api.hcnsec.cn     │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
     ┌────────────────────────────────────────────────────────────┐
     │                Execution & Self-Healing Loop               │
     │                                                            │
     │  [Click ID Selector] ──(Dynamic Shift)──> [Coordinate Tap] │
     │                                                            │
     │  Actions: Click, Type, Keypress, Select, Scroll, Download  │
     └─────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
                      Goal Achieved / Audit Report
```

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- Brave Browser (auto-detected) or bundled Chromium

### 2. Installation
```bash
# Clone the repository
git clone <repo-url>
cd agent-4

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser dependencies (if not using Brave)
python -m playwright install chromium
```

### 3. Configure API Key
Create a `.env` file in the root folder:
```env
# Your Gemini API Key
GEMINI_API_KEY=your_api_key_here


# Text-only mode (set to true for non-vision models)
TEXT_ONLY_MODE=true

# Model name
GEMINI_MODEL=gemini-2.5-flash
HEADLESS=false
```

---

## 🦁 Using Your Real Brave Profile (Logged-In Accounts)

Because Brave/Chromium prevents two programs from locking the same `User Data` files at the same time, FRIDAY provides a dedicated command to connect directly to your real **Work** profile:

### Step 1: Connect Brave
```bash
python main.py connect-brave
```
This restarts Brave with remote debugging on port `9222`, opens your real **Work** profile, and restores your open tabs.

### Step 2: Run Any Task!
```bash
python main.py run "Go to github.com and check my notifications"
```
FRIDAY will attach directly to your open Brave window, using all your active logins and sessions!

---

## 💻 CLI Commands & Usage

| Command | Description |
|---|---|
| `python main.py connect-brave` | Starts/Restarts Brave with port 9222 on your real profile. |
| `python main.py run "<task>"` | Runs a natural language browser task. |
| `python main.py run "<task>" --headed` | Runs task with a visible browser window. |
| `python main.py run "<task>" --new-profile` | Runs in an isolated profile instead of your real profile. |
| `python main.py interactive` | Opens an interactive conversational session. |
| `python main.py test-browser` | Runs automated smoke tests verifying DOM harvesting and clicks. |

### Examples:

```bash
# Watch FRIDAY search and extract headlines live:
python main.py run "Go to news.ycombinator.com and extract the top 3 headlines" --headed

# Research a topic:
python main.py run "Go to wikipedia.org, search for Quantum Computing, and summarize the intro" --headed

# Interactive REPL:
python main.py interactive --headed
```

---

## 📁 Repository Structure

```
friday/
├── agent.py               # FRIDAY core perception-reasoning-action orchestrator
├── browser_manager.py     # Playwright engine (Brave detection, CDP attachment, clicks/typing)
├── dom_annotator.py       # Set-of-Marks DOM labeling and page text extractor
├── actions.py             # Pydantic schemas for structured agent actions
├── config.py              # Environment configuration & Brave auto-detection
├── main.py                # Command-line interface (run, interactive, connect-brave, test-browser)
├── requirements.txt       # Dependencies
├── .gitignore             # Comprehensive privacy & artifact exclusions
├── .env.example           # Environment variable template
├── examples/
│   ├── extract_quotes.py  # Structured data extraction example
│   └── download_file.py   # Autonomous download example
└── tests/
    └── test_agent.py      # Automated smoke test suite
```

---

## 🛡️ Privacy & Safety
- **Local Auditing**: Viewport snapshots for each step are stored locally in `screenshots/` for full visual verification.
- **Step Caps**: Tasks default to a maximum of 25 steps to prevent runaway execution.
