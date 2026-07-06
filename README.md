# Nova — AI Personal Productivity Assistant

Nova is an autonomous personal productivity assistant, planner, scheduler, and accountability partner built using the **Google Agent Development Kit (ADK)** and the **Model Context Protocol (MCP)**. 

Featuring a modern Glassmorphism-style dashboard frontend, an AI-powered coach, and a robust backend agent with 28 custom productivity tools, Nova helps users seamlessly manage their tasks, categories, goals, habits, and daily schedules.

---

## 🌟 Core Features

- **Autonomous Agent Chat:** Live AI Chat with a state-aware agent powered by `gemini-2.5-flash` to query, create, or modify your agenda naturally.
- **Dynamic Category System:** Create, edit, rename, and delete custom categories in a fully dynamic database-backed management system.
- **Interactive Task Editor:** Comprehensive task modification panel to update titles, categories, priorities, due dates, reminder times, and statuses.
- **Conflict Detection & AI Coach:** Personalized daily productivity reviews and conflict alerts to optimize your schedule.
- **Notification Synchronization:** Real-time notification updates that instantly clear when tasks are deleted, completed, or updated.
- **Interactive Calendar & Dashboard:** Fully responsive scheduling overview and quick checklist manager with zero-cache page refreshing.

---

## 📂 Repository Structure

```text
my-first-project/
├── .gitignore                 # Root level gitignore
├── README.md                  # Root README (this file)
└── nova/                      # Nova application package
    ├── app/                   # Backend agent & server
    │   ├── agent.py           # ADK Agent definition & Gemini model configuration
    │   ├── fast_api_app.py    # FastAPI routes (chat endpoints, category endpoints)
    │   ├── tools.py           # Core agent business logic & 28 productivity tools
    │   ├── store.py           # SQLite database store & CRUD operations
    │   └── database.py        # Database schema migrations
    ├── frontend/              # Frontend React application
    │   ├── src/
    │   │   ├── App.jsx        # Dashboard SPA interface
    │   │   └── App.css        # Glassmorphism design system styles
    │   └── vite.config.js     # Frontend builder configuration
    ├── tests/                 # Unit & integration tests
    └── pyproject.toml         # Backend dependencies & virtual environment settings
```

---

## 🛠️ Requirements

Ensure you have the following installed on your machine:
- **Python ≥ 3.11** (Required by Google ADK)
- **uv** (Astral Python package manager)
- **Node.js ≥ 18** (For the Vite/React dashboard)
- **Google Gemini API Key** (Set `GOOGLE_API_KEY` in environment)

---

## 🚀 Quick Start

### 1. Link your API Key
Configure your Gemini API key in `nova/app/.env` or export it to your terminal:
```bash
export GOOGLE_API_KEY="your-gemini-api-key"
```

### 2. Run the Backend Server
Navigate to the `nova` folder and start the FastAPI server:
```bash
cd nova
uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000
```
*The REST API will be available at `http://localhost:8000`.*

### 3. Run the Frontend Dashboard
Open a new terminal window, navigate to the frontend folder, and launch the dev server:
```bash
cd nova/frontend
npm install
npm run dev
```
*The Vite dashboard will launch locally. Check the terminal output for the active port (usually `http://localhost:5173`).*

---

## 🧪 Running Tests & Evaluation

To run pytest and ADK quality evaluations, use Astral `uv`:

```bash
cd nova
# Run all unit & integration tests
uv run pytest tests/unit tests/integration

# Run ADK Quality Evaluation dataset
uv run agents-cli eval run
```

For detailed information about the standalone MCP server, deployment, and Cloud observability setup, see the **[Backend README](file:///Users/mohammadwasim/Desktop/my-first-project/nova/README.md)**.
