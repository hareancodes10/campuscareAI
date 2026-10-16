# CampusCare AI — Smart Campus Support Assistant

A polished, full-stack prototype for the capstone problem statement:

> Students and staff may not know how to properly categorize and communicate technical or administrative issues when requesting support.

CampusCare turns plain-language complaints into clearer support tickets, recommends a campus category and department, suggests priority, saves tickets to SQLite, and provides an admin-style inbox to track and update them.

## Features

- Responsive dashboard with ticket statistics and category breakdowns
- New ticket form with name, email, role, title, and description
- Nexus API integration using an OpenAI-compatible Chat Completions endpoint
- AI categorization, department recommendation, priority suggestion, and description rewriting
- Local smart-rule fallback when no Nexus API is configured or the provider is unavailable
- SQLite persistence
- Search and filter the ticket inbox
- Ticket details and activity history
- Update status and priority
- Safe environment-variable configuration for API credentials

## Requirements

- Python 3.10 or newer
- Internet access for installing packages and for Nexus AI calls
- A Nexus API key and its OpenAI-compatible base URL for live AI mode (optional; local fallback works without it)

## Run on Windows

1. Extract the ZIP into a folder, for example `D:\CampusCareAI`.
2. Open that folder in VS Code.
3. Open **Terminal → New Terminal**.
4. Create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

5. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, use Command Prompt terminal and run:

   ```bat
   .venv\Scripts\activate.bat
   ```

6. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

7. Optional: configure Nexus AI. Copy `.env.example` to `.env` and fill in the values from the Nexus platform's API documentation:

   ```env
   NEXUS_API_KEY=your_actual_key_here
   NEXUS_BASE_URL=https://your-provider-base-url/v1
   NEXUS_MODEL=gpt-4.1-nano
   ```

   The base URL above is a placeholder shape, not a verified Nexus endpoint. Use the exact base URL documented for the API key you received. Do not put the key in frontend JavaScript, upload `.env`, or share it publicly.

8. Start the app:

   ```powershell
   python app.py
   ```

9. Open **https://campuscareai-8z9e.onrender.com/** in your browser.

The SQLite database `campuscare.db` is created automatically on first start. Keep the terminal open while using the app.

## How Nexus integration works

The backend reads `NEXUS_API_KEY`, `NEXUS_BASE_URL`, and `NEXUS_MODEL` from `.env`. It sends a request to `<NEXUS_BASE_URL>/chat/completions` using bearer-token authentication and requests JSON output in the prompt. This assumes your Nexus service exposes an OpenAI-compatible Chat Completions endpoint. If the provider uses a different endpoint, authentication header, or request format, adapt `nexus_analysis()` in `app.py` to the provider's documentation.

Use the model identifier exactly as it appears in your Nexus dashboard. The group message lists `gpt-4.1-nano`; verify that exact ID is enabled for your key. The app displays Local fallback mode when the Nexus credentials are not configured. A ticket is never falsely marked as AI-generated: the `ai_used` flag is true only when the Nexus request succeeds.

## Demo walkthrough

1. Open the overview and show the dashboard.
2. Choose **Create a ticket**.
3. Enter a sample request such as:
   - Title: `Unable to access student portal`
   - Description: `I cannot log in to the student portal and my assignment submission deadline is today. I tried resetting my password but the page keeps loading.`
4. Select **Analyse with AI** to display the suggested category, department, priority, and clearer description.
5. Submit the ticket.
6. Open **Ticket inbox**, search for it, open the ticket, and change the status to `In Progress` or `Resolved`.
7. Return to Overview to show the updated metrics.

## Project structure

```text
CampusCareAI/
├── app.py                 # Flask API, Nexus integration, SQLite data layer
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── static/
    ├── index.html         # Frontend layout
    ├── styles.css         # Responsive visual design
    └── app.js             # Frontend behaviour and API calls
```

## API endpoints

- `GET /api/health` — backend and Nexus configuration status
- `GET /api/meta` — available categories and statuses
- `POST /api/analyze` — analyze a title and description
- `POST /api/tickets` — create and analyze a ticket
- `GET /api/tickets` — list/search/filter tickets
- `GET /api/tickets/<id>` — ticket details and activity history
- `PATCH /api/tickets/<id>` — update ticket status and priority
- `GET /api/stats` — dashboard metrics

## prototype screenshot
<img width="1903" height="974" alt="image" src="https://github.com/user-attachments/assets/37f813ac-1753-4c31-aca0-eb36e9647248" />



- This is a local college demo, not a production helpdesk. It does not include authentication/role-based access, email notifications, college SSO, or real ticket dispatch to campus departments.
- The ticket inbox is an admin-style demo interface and is not protected by login. Do not expose it publicly with real student information.
- The local fallback uses keyword rules, not an LLM. To demonstrate Nexus use, configure a valid API key, provider base URL, and model, then check the mode label after analysis.
- Validate the provider's endpoint format and model availability before the presentation.
