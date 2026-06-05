import os
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import bcrypt
from dotenv import load_dotenv

from .models import db, User, Employee, Project, ProjectMember, Task, ActivityLog, Notification
from .seed import seed_database

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DOCS_DIR = os.path.join(BASE_DIR, "docs")


def create_app():
    app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "jwt-dev-secret")
    db_url = os.getenv("DATABASE_URL", "sqlite:///projectace.db")
    if not db_url.startswith("sqlite"):
        db_url = "sqlite:///projectace.db"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    CORS(app, origins=["*"])
    db.init_app(app)
    JWTManager(app)

    def role_required(*roles):
        def decorator(fn):
            @wraps(fn)
            @jwt_required()
            def wrapper(*args, **kwargs):
                user = User.query.get(int(get_jwt_identity()))
                if not user or user.role not in roles:
                    return jsonify({"error": "Forbidden"}), 403
                return fn(user, *args, **kwargs)
            return wrapper
        return decorator

    def log_activity(user_id, action, entity_type, entity_id, message):
        db.session.add(ActivityLog(user_id=user_id, action=action, entity_type=entity_type,
                                 entity_id=entity_id, message=message))

    def user_json(u):
        emp = Employee.query.filter_by(user_id=u.id).first()
        return {"id": u.id, "name": u.name, "email": u.email, "role": u.role,
                "department": emp.department if emp else None, "position": emp.position if emp else None}

    def task_json(t):
        assignee = User.query.get(t.assigned_to) if t.assigned_to else None
        return {
            "id": t.id, "title": t.title, "description": t.description or "",
            "status": t.status, "priority": t.priority, "project_id": t.project_id,
            "assigned_to": t.assigned_to, "assignee_name": assignee.name if assignee else None,
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "position": t.position,
            "overdue": bool(t.deadline and t.deadline < datetime.utcnow() and t.status != "DONE"),
        }

    def can_access_project(user, project_id):
        if user.role == "ADMIN":
            return True
        if ProjectMember.query.filter_by(project_id=project_id, user_id=user.id).first():
            return True
        p = Project.query.get(project_id)
        return p and p.manager_id == user.id

    @app.route("/api/v1/health")
    def health():
        return jsonify({"status": "ok", "app": "ProjectAce POC"})

    @app.route("/api/v1/auth/login", methods=["POST"])
    def login():
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return jsonify({"error": "Invalid credentials"}), 401
        token = create_access_token(identity=str(user.id))
        return jsonify({"access_token": token, "user": user_json(user)})

    @app.route("/api/v1/auth/me")
    @jwt_required()
    def me():
        user = User.query.get(int(get_jwt_identity()))
        return jsonify(user_json(user))

    @app.route("/api/v1/projects")
    @jwt_required()
    def list_projects():
        user = User.query.get(int(get_jwt_identity()))
        if user.role == "ADMIN":
            projects = Project.query.all()
        else:
            member_ids = [m.project_id for m in ProjectMember.query.filter_by(user_id=user.id)]
            projects = Project.query.filter(
                (Project.id.in_(member_ids)) | (Project.manager_id == user.id)
            ).all()
        return jsonify([{
            "id": p.id, "name": p.name, "description": p.description or "",
            "status": p.status, "deadline": p.deadline.isoformat() if p.deadline else None,
            "manager_id": p.manager_id,
        } for p in projects])

    @app.route("/api/v1/projects", methods=["POST"])
    @role_required("ADMIN", "MANAGER")
    def create_project(user):
        data = request.get_json() or {}
        p = Project(name=data.get("name", "New Project"), description=data.get("description", ""),
                    status="ACTIVE", manager_id=user.id if user.role == "MANAGER" else data.get("manager_id", user.id))
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(project_id=p.id, user_id=user.id))
        log_activity(user.id, "CREATED", "project", p.id, f"Created project {p.name}")
        db.session.commit()
        return jsonify({"id": p.id}), 201

    @app.route("/api/v1/projects/<int:pid>/board")
    @jwt_required()
    def board(pid):
        user = User.query.get(int(get_jwt_identity()))
        if not can_access_project(user, pid):
            return jsonify({"error": "Forbidden"}), 403
        tasks = Task.query.filter_by(project_id=pid).order_by(Task.status, Task.position).all()
        grouped = {"TODO": [], "IN_PROGRESS": [], "DONE": []}
        for t in tasks:
            grouped.setdefault(t.status, []).append(task_json(t))
        return jsonify(grouped)

    @app.route("/api/v1/projects/<int:pid>/tasks", methods=["POST"])
    @role_required("ADMIN", "MANAGER")
    def create_task(user, pid):
        if not can_access_project(user, pid):
            return jsonify({"error": "Forbidden"}), 403
        data = request.get_json() or {}
        t = Task(title=data.get("title", "New task"), description=data.get("description", ""),
                 status=data.get("status", "TODO"), priority=data.get("priority", "MEDIUM"),
                 project_id=pid, assigned_to=data.get("assigned_to"), position=data.get("position", 0))
        db.session.add(t)
        log_activity(user.id, "CREATED", "task", None, f"Created task {t.title}")
        if t.assigned_to:
            db.session.add(Notification(user_id=t.assigned_to, title="Task assigned", body=f"Assigned: {t.title}"))
        db.session.commit()
        return jsonify(task_json(t)), 201

    @app.route("/api/v1/tasks/<int:tid>/move", methods=["PATCH"])
    @jwt_required()
    def move_task(tid):
        user = User.query.get(int(get_jwt_identity()))
        t = Task.query.get_or_404(tid)
        if not can_access_project(user, t.project_id):
            return jsonify({"error": "Forbidden"}), 403
        if user.role == "EMPLOYEE" and t.assigned_to != user.id:
            return jsonify({"error": "Employees can only move own tasks"}), 403
        data = request.get_json() or {}
        t.status = data.get("status", t.status)
        t.position = data.get("position", t.position)
        log_activity(user.id, "STATUS_CHANGED", "task", t.id, f"Moved {t.title} to {t.status}")
        db.session.commit()
        return jsonify(task_json(t))

    @app.route("/api/v1/dashboard/stats")
    @jwt_required()
    def dashboard_stats():
        user = User.query.get(int(get_jwt_identity()))
        if user.role == "EMPLOYEE":
            tasks = Task.query.filter_by(assigned_to=user.id).all()
            projects = len({t.project_id for t in tasks})
        elif user.role == "MANAGER":
            pids = [p.id for p in Project.query.filter_by(manager_id=user.id)]
            tasks = Task.query.filter(Task.project_id.in_(pids)).all() if pids else []
            projects = len(pids)
        else:
            tasks = Task.query.all()
            projects = Project.query.filter_by(status="ACTIVE").count()
        done = sum(1 for t in tasks if t.status == "DONE")
        overdue = sum(1 for t in tasks if t.deadline and t.deadline < datetime.utcnow() and t.status != "DONE")
        return jsonify({
            "active_projects": projects if user.role != "ADMIN" else Project.query.filter_by(status="ACTIVE").count(),
            "total_tasks": len(tasks),
            "completed_tasks": done,
            "overdue_tasks": overdue,
        })

    @app.route("/api/v1/dashboard/charts")
    @jwt_required()
    def dashboard_charts():
        user = User.query.get(int(get_jwt_identity()))
        if user.role == "EMPLOYEE":
            tasks = Task.query.filter_by(assigned_to=user.id).all()
        elif user.role == "MANAGER":
            pids = [p.id for p in Project.query.filter_by(manager_id=user.id)]
            tasks = Task.query.filter(Task.project_id.in_(pids)).all() if pids else []
        else:
            tasks = Task.query.all()
        by_status = {"TODO": 0, "IN_PROGRESS": 0, "DONE": 0}
        by_priority = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for t in tasks:
            by_status[t.status] = by_status.get(t.status, 0) + 1
            by_priority[t.priority] = by_priority.get(t.priority, 0) + 1
        return jsonify({"by_status": by_status, "by_priority": by_priority})

    @app.route("/api/v1/employees")
    @role_required("ADMIN")
    def employees(user):
        rows = db.session.query(User, Employee).outerjoin(Employee, Employee.user_id == User.id).filter(User.role != "ADMIN").all()
        return jsonify([{
            "user_id": u.id, "name": u.name, "email": u.email, "role": u.role,
            "department": e.department if e else None, "position": e.position if e else None,
        } for u, e in rows])

    @app.route("/api/v1/activity")
    @jwt_required()
    def activity():
        logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(50).all()
        return jsonify([{
            "id": a.id, "message": a.message, "action": a.action,
            "created_at": a.created_at.isoformat(),
        } for a in logs])

    @app.route("/api/v1/notifications")
    @jwt_required()
    def notifications():
        user = User.query.get(int(get_jwt_identity()))
        notes = Notification.query.filter_by(user_id=user.id).order_by(Notification.id.desc()).limit(20).all()
        return jsonify([{"id": n.id, "title": n.title, "body": n.body, "read": n.read_at is not None} for n in notes])

    @app.route("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/docs/manual")
    def manual():
        return send_from_directory(DOCS_DIR, "user-manual.html")

    @app.route("/docs/future-plan")
    def future_plan():
        return send_from_directory(BASE_DIR, "future-plan.html")

    @app.route("/docs/developer-guide")
    def developer_guide():
        return send_from_directory(DOCS_DIR, "developer-guide.html")

    with app.app_context():
        db.create_all()
        seed_database()

    return app
