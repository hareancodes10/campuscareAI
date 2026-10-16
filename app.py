import os
import json
import sqlite3
import re
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

app = Flask(__name__, static_folder="static")
DB_PATH = ROOT / "campuscare.db"

CATEGORIES = {
    "Technical Support": ["IT Helpdesk", "Portal login, Wi-Fi, email, software, account or device issues"],
    "Academic Support": ["Academic Office", "Course registration, timetable, attendance, exams or academic records"],
    "Administration": ["Student Administration", "Certificates, fees, ID cards, records or other administrative requests"],
    "Facilities & Maintenance": ["Campus Facilities", "Classroom equipment, electricity, water, furniture or campus infrastructure"],
    "Safety & Security": ["Campus Security", "Safety concerns, access issues or security-related incidents"],
    "Other": ["General Support", "Issues that do not fit another category"]
}
PRIORITIES = {"Low", "Medium", "High", "Urgent"}
STATUSES = {"Open", "In Progress", "Resolved", "Closed"}


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                improved_description TEXT NOT NULL,
                category TEXT NOT NULL,
                department TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                ai_summary TEXT NOT NULL DEFAULT '',
                ai_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(ticket_id) REFERENCES tickets(id)
            )
        """)


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def heuristic_analysis(title, description, role):
    text = f"{title} {description}".lower()
    rules = [
        ("Technical Support", ["login", "log in", "password", "portal", "wifi", "wi-fi", "internet", "email", "computer", "software", "printer", "network", "account", "website", "lms", "system"]),
        ("Academic Support", ["exam", "examination", "attendance", "timetable", "course", "subject", "marks", "grade", "faculty", "assignment", "registration", "semester", "class"]),
        ("Administration", ["fee", "fees", "payment", "certificate", "id card", "identity card", "scholarship", "transcript", "document", "bonafide", "records", "admission"]),
        ("Facilities & Maintenance", ["broken", "projector", "fan", "light", "electricity", "water", "toilet", "desk", "chair", "classroom", "leak", "maintenance", "ac ", "air conditioner"]),
        ("Safety & Security", ["unsafe", "harassment", "security", "threat", "emergency", "lost item", "theft", "injury", "accident"])
    ]
    category = "Other"
    best = 0
    for cat, words in rules:
        score = sum(1 for w in words if w in text)
        if score > best:
            category, best = cat, score

    urgent_words = ["emergency", "danger", "fire", "injury", "threat", "unsafe", "security breach"]
    high_words = ["deadline", "today", "unable to attend", "exam", "submission", "multiple students", "entire class", "cannot access"]
    if any(w in text for w in urgent_words):
        priority = "Urgent"
    elif any(w in text for w in high_words):
        priority = "High"
    elif category in ("Technical Support", "Facilities & Maintenance"):
        priority = "Medium"
    else:
        priority = "Low"

    department = CATEGORIES[category][0]
    cleaned = re.sub(r"\s+", " ", description).strip()
    improved = cleaned[0].upper() + cleaned[1:] if cleaned else title
    if improved and improved[-1] not in ".!?":
        improved += "."
    summary = f"{category} request routed to {department}. Suggested priority: {priority}."
    return {
        "category": category,
        "department": department,
        "priority": priority,
        "improved_description": improved,
        "summary": summary,
        "ai_used": False,
        "mode": "Local smart rules"
    }


def nexus_analysis(title, description, role):
    api_key = os.getenv("NEXUS_API_KEY", "").strip()
    base_url = os.getenv("NEXUS_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("NEXUS_MODEL", "gpt-4.1-nano").strip()
    if not api_key or not base_url:
        return heuristic_analysis(title, description, role)

    system_prompt = """You are CampusCare, an assistant that helps university students and staff communicate support issues clearly.
Return ONLY valid JSON with keys: category, department, priority, improved_description, summary.
Allowed categories: Technical Support, Academic Support, Administration, Facilities & Maintenance, Safety & Security, Other.
Allowed departments: IT Helpdesk, Academic Office, Student Administration, Campus Facilities, Campus Security, General Support.
Allowed priorities: Low, Medium, High, Urgent.
Be conservative with Urgent: reserve it for immediate safety/security risks or serious emergencies. Do not invent facts. Rewrite the description professionally while preserving the user's meaning. The department must match the category. The summary should be one concise sentence."""
    user_prompt = f"Role: {role}\nTitle: {title}\nIssue description: {description}"
    endpoint = base_url if base_url.endswith("/chat/completions") else base_url + "/chat/completions"
    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            },
            timeout=25
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
        data = json.loads(content)
        category = data.get("category", "Other")
        if category not in CATEGORIES:
            category = "Other"
        priority = data.get("priority", "Medium")
        if priority not in PRIORITIES:
            priority = "Medium"
        department = CATEGORIES[category][0]
        return {
            "category": category,
            "department": department,
            "priority": priority,
            "improved_description": str(data.get("improved_description") or description)[:4000],
            "summary": str(data.get("summary") or f"{category} request routed to {department}.")[:500],
            "ai_used": True,
            "mode": f"Nexus AI · {model}"
        }
    except Exception as exc:
        # Keep ticket submission available if provider config/network/model response fails.
        result = heuristic_analysis(title, description, role)
        result["mode"] = "Local fallback (Nexus request unavailable)"
        result["notice"] = "Nexus AI could not be reached or returned an unexpected response. Local categorization was used."
        return result


def row_to_dict(row):
    item = dict(row)
    item["ai_used"] = bool(item.get("ai_used"))
    return item


@app.get("/")
def home():
    return send_from_directory("static", "index.html")


@app.get("/api/health")
def health():
    configured = bool(os.getenv("NEXUS_API_KEY", "").strip() and os.getenv("NEXUS_BASE_URL", "").strip())
    return jsonify({"ok": True, "nexus_configured": configured, "model": os.getenv("NEXUS_MODEL", "gpt-4.1-nano")})


@app.get("/api/meta")
def meta():
    return jsonify({
        "categories": [{"name": k, "department": v[0], "description": v[1]} for k, v in CATEGORIES.items()],
        "statuses": sorted(STATUSES)
    })


@app.post("/api/analyze")
def analyze():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    role = str(payload.get("role", "Student")).strip()
    if len(title) < 4 or len(description) < 10:
        return jsonify({"error": "Enter a title (at least 4 characters) and description (at least 10 characters)."}), 400
    if len(title) > 160 or len(description) > 4000:
        return jsonify({"error": "Title must be under 160 characters and description under 4,000 characters."}), 400
    return jsonify(nexus_analysis(title, description, role))


@app.post("/api/tickets")
def create_ticket():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip()
    role = str(payload.get("role", "Student")).strip()
    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    if not name or not email or not title or len(description) < 10:
        return jsonify({"error": "Please provide your name, email, title, and a description of at least 10 characters."}), 400
    if len(name) > 120 or len(email) > 180 or len(title) > 160 or len(description) > 4000:
        return jsonify({"error": "One or more fields exceed the allowed length."}), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    analysis = nexus_analysis(title, description, role)
    created = now()
    with connect_db() as conn:
        cur = conn.execute("""
            INSERT INTO tickets
            (name,email,role,title,description,improved_description,category,department,priority,status,ai_summary,ai_used,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            name, email, role, title, description, analysis["improved_description"],
            analysis["category"], analysis["department"], analysis["priority"], "Open",
            analysis["summary"], int(analysis["ai_used"]), created, created
        ))
        ticket_id = cur.lastrowid
        conn.execute("INSERT INTO activity(ticket_id,message,created_at) VALUES(?,?,?)",
                     (ticket_id, "Ticket created. " + analysis["summary"], created))
        row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    result = row_to_dict(row)
    if analysis.get("notice"):
        result["notice"] = analysis["notice"]
    result["mode"] = analysis["mode"]
    return jsonify(result), 201


@app.get("/api/tickets")
def list_tickets():
    status = request.args.get("status", "").strip()
    category = request.args.get("category", "").strip()
    search = request.args.get("q", "").strip()[:100]
    query = "SELECT * FROM tickets WHERE 1=1"
    args = []
    if status in STATUSES:
        query += " AND status=?"
        args.append(status)
    if category in CATEGORIES:
        query += " AND category=?"
        args.append(category)
    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR name LIKE ? OR CAST(id AS TEXT) LIKE ?)"
        pattern = f"%{search}%"
        args.extend([pattern, pattern, pattern, pattern])
    query += " ORDER BY CASE priority WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, id DESC LIMIT 200"
    with connect_db() as conn:
        rows = conn.execute(query, args).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.get("/api/tickets/<int:ticket_id>")
def get_ticket(ticket_id):
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not row:
            return jsonify({"error": "Ticket not found."}), 404
        events = conn.execute("SELECT message,created_at FROM activity WHERE ticket_id=? ORDER BY id DESC", (ticket_id,)).fetchall()
    item = row_to_dict(row)
    item["activity"] = [dict(e) for e in events]
    return jsonify(item)


@app.patch("/api/tickets/<int:ticket_id>")
def update_ticket(ticket_id):
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status", "")).strip()
    priority = str(payload.get("priority", "")).strip()
    if status not in STATUSES:
        return jsonify({"error": "Choose a valid status."}), 400
    if priority and priority not in PRIORITIES:
        return jsonify({"error": "Choose a valid priority."}), 400
    with connect_db() as conn:
        old = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not old:
            return jsonify({"error": "Ticket not found."}), 404
        new_priority = priority or old["priority"]
        conn.execute("UPDATE tickets SET status=?, priority=?, updated_at=? WHERE id=?",
                     (status, new_priority, now(), ticket_id))
        message = f"Status changed to {status}"
        if new_priority != old["priority"]:
            message += f"; priority changed to {new_priority}"
        conn.execute("INSERT INTO activity(ticket_id,message,created_at) VALUES(?,?,?)",
                     (ticket_id, message + ".", now()))
        row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    return jsonify(row_to_dict(row))


@app.get("/api/stats")
def stats():
    with connect_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        open_count = conn.execute("SELECT COUNT(*) FROM tickets WHERE status='Open'").fetchone()[0]
        progress = conn.execute("SELECT COUNT(*) FROM tickets WHERE status='In Progress'").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved','Closed')").fetchone()[0]
        urgent = conn.execute("SELECT COUNT(*) FROM tickets WHERE priority IN ('Urgent','High') AND status NOT IN ('Resolved','Closed')").fetchone()[0]
        cats = conn.execute("SELECT category, COUNT(*) count FROM tickets GROUP BY category ORDER BY count DESC").fetchall()
        recent = conn.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 5").fetchall()
    return jsonify({
        "total": total, "open": open_count, "in_progress": progress,
        "resolved": resolved, "high_priority": urgent,
        "categories": [{"category": r["category"], "count": r["count"]} for r in cats],
        "recent": [row_to_dict(r) for r in recent]
    })


if __name__ == "__main__":
    init_db()
    print("\\nCampusCare AI is starting at http://127.0.0.1:5000")
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
