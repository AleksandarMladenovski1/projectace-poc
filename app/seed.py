from datetime import date, datetime, timedelta
import bcrypt
from .models import db, User, Employee, Project, ProjectMember, Task, ActivityLog, Notification


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()


def seed_database():
    if User.query.first():
        return

    admin = User(name="Admin User", email="admin@projectace.local", password_hash=_hash("admin123"), role="ADMIN")
    mgr1 = User(name="Mia Manager", email="manager@projectace.local", password_hash=_hash("manager123"), role="MANAGER")
    emp1 = User(name="Elena Employee", email="employee@projectace.local", password_hash=_hash("employee123"), role="EMPLOYEE")
    emp2 = User(name="Alex Dev", email="alex@projectace.local", password_hash=_hash("employee123"), role="EMPLOYEE")
    db.session.add_all([admin, mgr1, emp1, emp2])
    db.session.flush()

    for u, dept, pos in [(emp1, "Engineering", "Developer"), (emp2, "Engineering", "QA")]:
        db.session.add(Employee(user_id=u.id, department=dept, position=pos))

    p1 = Project(name="Website Redesign", description="Marketing site refresh", status="ACTIVE",
                 deadline=date.today() + timedelta(days=30), manager_id=mgr1.id)
    p2 = Project(name="Mobile App MVP", description="iOS/Android POC", status="ACTIVE",
                 deadline=date.today() + timedelta(days=14), manager_id=mgr1.id)
    db.session.add_all([p1, p2])
    db.session.flush()

    for pid, uid in [(p1.id, mgr1.id), (p1.id, emp1.id), (p1.id, emp2.id), (p2.id, mgr1.id), (p2.id, emp1.id)]:
        db.session.add(ProjectMember(project_id=pid, user_id=uid))

    tasks = [
        Task(title="Setup repo", status="DONE", priority="HIGH", project_id=p1.id, assigned_to=emp1.id, position=0,
             deadline=datetime.utcnow() - timedelta(days=2)),
        Task(title="Design mockups", status="IN_PROGRESS", priority="MEDIUM", project_id=p1.id, assigned_to=emp2.id, position=0,
             deadline=datetime.utcnow() + timedelta(days=3)),
        Task(title="API integration", status="TODO", priority="HIGH", project_id=p1.id, assigned_to=emp1.id, position=0,
             deadline=datetime.utcnow() - timedelta(days=1)),
        Task(title="Auth module", status="IN_PROGRESS", priority="HIGH", project_id=p2.id, assigned_to=emp1.id, position=0),
        Task(title="Beta testing", status="TODO", priority="LOW", project_id=p2.id, assigned_to=emp2.id, position=0),
    ]
    db.session.add_all(tasks)
    db.session.add(ActivityLog(user_id=mgr1.id, action="CREATED", entity_type="project", entity_id=p1.id,
                               message="Created project Website Redesign"))
    db.session.add(Notification(user_id=emp1.id, title="Task assigned", body="You were assigned: API integration"))
    db.session.commit()
