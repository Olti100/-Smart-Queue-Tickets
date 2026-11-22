from __future__ import annotations

from datetime import datetime, timedelta
from functools import wraps
from os import getenv

import bcrypt
from config import DB_PATH
import csv
import io
from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from sqlalchemy import desc, func, or_, select

from core.analytics_engine import AnalyticsEngine
from core.queue_engine import QueueEngine
from core.wait_predictor import WaitPredictor
from database.bootstrap import bootstrap_database
from database.connection import get_session
from database.models import (
    Counter,
    CustomerFeedback,
    Department,
    PriorityCategory,
    QueueMetric,
    Role,
    Service,
    Setting,
    Ticket,
    TicketEvent,
    TicketStatus,
    User,
)
from services.ticket_service import TicketService


bootstrap_database()
app = Flask(__name__)
app.config["SECRET_KEY"] = getenv("SMART_QUEUE_SECRET", "smart-queue-local-dev-secret")


def _verify_password(raw_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(raw_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _current_user(db_session):
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db_session.get(User, user_id)


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def roles_required(*roles: Role):
    role_values = {role.value for role in roles}

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user_role = session.get("user_role")
            if user_role not in role_values:
                flash("You do not have access to this page.", "danger")
                return redirect(url_for("home"))
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


@app.get("/")
def home():
    if not session.get("user_id"):
        return redirect(url_for("customer_portal"))

    role = session.get("user_role")
    if role in {Role.ADMIN.value, Role.MANAGER.value}:
        return redirect(url_for("manager_dashboard"))
    if role == Role.RECEPTIONIST.value:
        return redirect(url_for("receptionist_dashboard"))
    if role == Role.STAFF.value:
        return redirect(url_for("staff_dashboard"))
    return redirect(url_for("customer_portal"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with get_session() as db:
            user = db.scalar(select(User).where(User.username == username, User.is_active.is_(True)))
            if user and _verify_password(password, user.password_hash):
                session["user_id"] = user.id
                session["user_name"] = user.full_name
                session["user_role"] = user.role.value
                flash("Welcome back.", "success")
                return redirect(url_for("home"))

        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("customer_portal"))


@app.route("/customer", methods=["GET", "POST"])
def customer_portal():
    tracked = None
    with get_session() as db:
        departments = list(db.scalars(select(Department).where(Department.is_active.is_(True))).all())
        services = list(db.scalars(select(Service).where(Service.is_active.is_(True))).all())

        predictor = WaitPredictor(db)
        weather = predictor.queue_weather()

        if request.method == "POST":
            action = request.form.get("action")

            if action == "generate":
                department_id = int(request.form["department_id"])
                service_id = int(request.form["service_id"])
                customer_name = request.form.get("customer_name", "").strip() or None
                priority = PriorityCategory(request.form.get("priority", PriorityCategory.REGULAR.value))

                service = TicketService(db)
                ticket = service.create_ticket(
                    department_id=department_id,
                    service_id=service_id,
                    customer_name=customer_name,
                    priority_category=priority,
                    created_by_user_id=session.get("user_id"),
                )
                flash(f"Ticket generated successfully: {ticket.ticket_number}", "success")
                return redirect(url_for("customer_portal", ticket=ticket.ticket_number))

            if action == "track":
                number = request.form.get("ticket_number", "").strip().upper()
                if number:
                    try:
                        tracked = QueueEngine(db).ticket_snapshot(number)
                    except ValueError:
                        flash("Ticket not found.", "danger")

            if action == "feedback":
                number = request.form.get("feedback_ticket", "").strip().upper()
                rating = int(request.form.get("rating", "5"))
                comment = request.form.get("comment", "").strip() or None
                ticket = db.scalar(select(Ticket).where(Ticket.ticket_number == number))
                if not ticket:
                    flash("Ticket not found for feedback.", "danger")
                else:
                    existing = db.scalar(select(CustomerFeedback).where(CustomerFeedback.ticket_id == ticket.id))
                    if existing:
                        existing.rating = rating
                        existing.comment = comment
                    else:
                        db.add(CustomerFeedback(ticket_id=ticket.id, rating=rating, comment=comment))
                    flash("Feedback submitted.", "success")

        ticket_query = request.args.get("ticket", "").strip().upper()
        if ticket_query and not tracked:
            try:
                tracked = QueueEngine(db).ticket_snapshot(ticket_query)
            except ValueError:
                tracked = None

        return render_template(
            "customer.html",
            departments=departments,
            services=services,
            tracked=tracked,
            priorities=[p.value for p in PriorityCategory],
            weather=weather,
        )


@app.route("/receptionist", methods=["GET", "POST"])
@login_required
@roles_required(Role.ADMIN, Role.MANAGER, Role.RECEPTIONIST)
def receptionist_dashboard():
    with get_session() as db:
        departments = list(db.scalars(select(Department).where(Department.is_active.is_(True))).all())
        services = list(db.scalars(select(Service).where(Service.is_active.is_(True))).all())

        if request.method == "POST":
            action = request.form.get("action")
            engine = QueueEngine(db)

            if action == "generate":
                ticket = TicketService(db).create_ticket(
                    department_id=int(request.form["department_id"]),
                    service_id=int(request.form["service_id"]),
                    customer_name=request.form.get("customer_name", "").strip() or None,
                    priority_category=PriorityCategory(request.form.get("priority", PriorityCategory.REGULAR.value)),
                    created_by_user_id=session.get("user_id"),
                )
                flash(f"Ticket generated: {ticket.ticket_number}", "success")

            elif action == "cancel":
                ticket_id = int(request.form["ticket_id"])
                try:
                    engine.cancel_ticket(ticket_id, session.get("user_id"), "Cancelled at reception")
                    flash("Ticket cancelled.", "warning")
                except ValueError:
                    flash("Ticket not found.", "danger")

            elif action == "transfer":
                ticket_id = int(request.form["ticket_id"])
                target_service_id = int(request.form["target_service_id"])
                target_service = db.get(Service, target_service_id)
                if not target_service:
                    flash("Invalid target service.", "danger")
                else:
                    engine.transfer_ticket(
                        ticket_id=ticket_id,
                        target_department_id=target_service.department_id,
                        target_service_id=target_service.id,
                        user_id=session.get("user_id"),
                        note="Transferred by receptionist",
                    )
                    flash("Ticket transferred.", "success")

            return redirect(url_for("receptionist_dashboard"))

        query = request.args.get("q", "").strip()
        status_filter = request.args.get("status", "ALL").strip().upper()
        department_filter = request.args.get("department_id", type=int)

        stmt = select(Ticket).order_by(desc(Ticket.created_at)).limit(100)
        if query:
            stmt = stmt.where(
                or_(
                    Ticket.ticket_number.ilike(f"%{query}%"),
                    Ticket.customer_name.ilike(f"%{query}%"),
                )
            )
        if status_filter != "ALL":
            try:
                stmt = stmt.where(Ticket.status == TicketStatus(status_filter))
            except ValueError:
                status_filter = "ALL"
        if department_filter:
            stmt = stmt.where(Ticket.department_id == department_filter)

        tickets = list(db.scalars(stmt).all())

        waiting_count = db.scalar(select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.WAITING)) or 0
        called_count = db.scalar(select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.CALLED)) or 0
        serving_count = db.scalar(select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.SERVING)) or 0
        completed_today = db.scalar(select(func.count(Ticket.id)).where(
            Ticket.status == TicketStatus.COMPLETED,
            Ticket.completed_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
        )) or 0

        reception_summary = {
            "waiting": waiting_count,
            "called": called_count,
            "serving": serving_count,
            "completed_today": completed_today,
        }

        return render_template(
            "receptionist.html",
            tickets=tickets,
            departments=departments,
            services=services,
            priorities=[p.value for p in PriorityCategory],
            query=query,
            status_filter=status_filter,
            department_filter=department_filter,
            reception_summary=reception_summary,
        )


@app.route("/staff", methods=["GET", "POST"])
@login_required
@roles_required(Role.ADMIN, Role.MANAGER, Role.STAFF)
def staff_dashboard():
    selected_counter_id = request.values.get("counter_id", type=int)

    with get_session() as db:
        counters = list(db.scalars(select(Counter).where(Counter.is_active.is_(True))).all())
        if not counters:
            flash("No active counters configured.", "warning")
            return render_template("staff.html", counters=[], selected_counter=None, current_ticket=None)

        if selected_counter_id is None:
            selected_counter_id = counters[0].id
        selected_counter = db.get(Counter, selected_counter_id)

        if request.method == "POST":
            action = request.form.get("action")
            engine = QueueEngine(db)
            staff_id = session.get("user_id")

            current_ticket = db.scalar(
                select(Ticket)
                .where(Ticket.counter_id == selected_counter.id, Ticket.status.in_([TicketStatus.CALLED, TicketStatus.SERVING]))
                .order_by(desc(Ticket.called_at), desc(Ticket.updated_at))
            )

            if action == "call_next":
                ticket = TicketService(db).call_next_ticket(selected_counter.id, staff_id)
                flash(f"Called {ticket.ticket_number}" if ticket else "No waiting tickets.", "info")
            elif action == "start" and current_ticket:
                engine.start_service(current_ticket.id, staff_id)
                flash("Service started.", "success")
            elif action == "complete" and current_ticket:
                engine.complete_service(current_ticket.id, staff_id)
                flash("Service completed.", "success")
            elif action == "recall" and current_ticket:
                engine.recall_ticket(current_ticket.id, staff_id)
                flash("Ticket recalled.", "info")
            elif action == "skip" and current_ticket:
                reason = request.form.get("skip_reason", "No response")
                engine.skip_ticket(current_ticket.id, staff_id, reason)
                flash("Ticket skipped.", "warning")
            elif action == "pause":
                engine.set_counter_pause(selected_counter.id, True)
                flash("Counter paused.", "warning")
            elif action == "resume":
                engine.set_counter_pause(selected_counter.id, False)
                flash("Counter resumed.", "success")

            return redirect(url_for("staff_dashboard", counter_id=selected_counter.id))

        current_ticket = db.scalar(
            select(Ticket)
            .where(Ticket.counter_id == selected_counter.id, Ticket.status.in_([TicketStatus.CALLED, TicketStatus.SERVING]))
            .order_by(desc(Ticket.called_at), desc(Ticket.updated_at))
        )

        waiting = list(
            db.scalars(
                select(Ticket)
                .where(Ticket.department_id == selected_counter.department_id, Ticket.status == TicketStatus.WAITING)
                .order_by(Ticket.created_at.asc())
                .limit(10)
            ).all()
        )

        waiting_count = len(waiting)
        next_ticket = waiting[0] if waiting else None
        completed_today = db.scalar(select(func.count(Ticket.id)).where(
            Ticket.counter_id == selected_counter.id,
            Ticket.status == TicketStatus.COMPLETED,
            Ticket.completed_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
        )) or 0

        completed_durations = []
        for ticket in db.scalars(select(Ticket).where(
            Ticket.counter_id == selected_counter.id,
            Ticket.status == TicketStatus.COMPLETED,
            Ticket.service_started_at.is_not(None),
            Ticket.completed_at.is_not(None),
        )).all():
            completed_durations.append((ticket.completed_at - ticket.service_started_at).total_seconds() / 60)
        average_service = round(sum(completed_durations) / len(completed_durations), 1) if completed_durations else 0

        elapsed_service = 0
        if current_ticket and current_ticket.service_started_at:
            elapsed_service = max(int((datetime.utcnow() - current_ticket.service_started_at).total_seconds() / 60), 0)

        staff_summary = {
            "waiting": waiting_count,
            "completed_today": completed_today,
            "average_service": average_service,
            "elapsed_service": elapsed_service,
            "next_ticket": next_ticket,
        }

        return render_template(
            "staff.html",
            counters=counters,
            selected_counter=selected_counter,
            current_ticket=current_ticket,
            waiting=waiting,
            staff_summary=staff_summary,
        )


@app.get("/display")
def public_display():
    with get_session() as db:
        departments = list(db.scalars(select(Department).where(Department.is_active.is_(True))).all())
        dep_id = request.args.get("department_id", type=int)

        engine = QueueEngine(db)
        called = engine.recent_calls(dep_id, limit=12)

        waiting_stmt = select(Ticket).where(Ticket.status == TicketStatus.WAITING).order_by(Ticket.created_at.asc()).limit(10)
        if dep_id:
            waiting_stmt = waiting_stmt.where(Ticket.department_id == dep_id)
        waiting = list(db.scalars(waiting_stmt).all())

        weather = WaitPredictor(db).queue_weather(dep_id)

        return render_template(
            "display.html",
            called=called,
            waiting=waiting,
            departments=departments,
            dep_id=dep_id,
            now=datetime.now(),
            weather=weather,
        )


@app.get("/manager")
@login_required
@roles_required(Role.ADMIN, Role.MANAGER)
def manager_dashboard():
    start = request.args.get("start")
    end = request.args.get("end")

    end_date = datetime.strptime(end, "%Y-%m-%d") if end else datetime.utcnow()
    start_date = datetime.strptime(start, "%Y-%m-%d") if start else (end_date - timedelta(days=7))

    with get_session() as db:
        analytics = AnalyticsEngine(db)
        kpis = analytics.kpis(start_date, end_date)
        peak_hours = analytics.peak_hours(start_date, end_date).to_dict("records")
        hourly_counts = {hour: 0 for hour in range(24)}
        for row in peak_hours:
            hourly_counts[int(row["hour"])] = int(row["tickets"])
        peak_hour_max = max(hourly_counts.values(), default=0) or 1
        peak_hour_bars = [
            {"hour": hour, "count": count, "height": round((count / peak_hour_max) * 100)}
            for hour, count in hourly_counts.items()
        ]

        predictor = WaitPredictor(db)
        weather = predictor.queue_weather()
        coach = predictor.smart_coach()

        tickets = list(db.scalars(
            select(Ticket).where(Ticket.created_at >= start_date, Ticket.created_at <= end_date)
        ).all())

        trend_days = []
        trend_values = []
        for offset in range(6, -1, -1):
            day = end_date.date() - timedelta(days=offset)
            count = sum(1 for ticket in tickets if ticket.created_at.date() == day)
            trend_days.append(day.strftime("%a"))
            trend_values.append(count)

        trend_max = max(trend_values, default=0) or 1
        trend_points = []
        for index, value in enumerate(trend_values):
            x = 20 + (index * (560 / 6))
            y = 180 - ((value / trend_max) * 140)
            trend_points.append({"x": round(x, 1), "y": round(y, 1), "value": value, "day": trend_days[index]})

        status_counts = {
            "Waiting": len([ticket for ticket in tickets if ticket.status == TicketStatus.WAITING]),
            "Serving": len([ticket for ticket in tickets if ticket.status in (TicketStatus.CALLED, TicketStatus.SERVING)]),
            "Completed": len([ticket for ticket in tickets if ticket.status == TicketStatus.COMPLETED]),
            "Other": len([ticket for ticket in tickets if ticket.status not in (
                TicketStatus.WAITING, TicketStatus.CALLED, TicketStatus.SERVING, TicketStatus.COMPLETED,
            )]),
        }
        status_total = sum(status_counts.values()) or 1
        status_mix = []
        status_offset = 0
        for name, count in status_counts.items():
            percent = round((count / status_total) * 100)
            status_mix.append({"name": name, "count": count, "percent": percent, "offset": status_offset})
            status_offset += percent

        status_gradient_parts = []
        gradient_start = 0
        gradient_colors = {"Waiting": "#f79009", "Serving": "#4f46e5", "Completed": "#16b364", "Other": "#98a2b3"}
        for item in status_mix:
            gradient_end = gradient_start + item["percent"]
            status_gradient_parts.append(f'{gradient_colors[item["name"]]} {gradient_start}% {gradient_end}%')
            gradient_start = gradient_end
        status_gradient = "conic-gradient(" + ",".join(status_gradient_parts) + ")"

        department_counts = {}
        for ticket in tickets:
            department_name = ticket.department.name if ticket.department else "Unknown"
            department_counts[department_name] = department_counts.get(department_name, 0) + 1
        department_mix = sorted(
            ({"name": name, "count": count} for name, count in department_counts.items()),
            key=lambda item: item["count"],
            reverse=True,
        )[:6]

        counter_stats = []
        counters = list(db.scalars(select(Counter).where(Counter.is_active.is_(True))).all())
        for counter in counters:
            waiting_count = db.scalar(select(func.count(Ticket.id)).where(
                Ticket.counter_id == counter.id,
                Ticket.status.in_((TicketStatus.CALLED, TicketStatus.SERVING)),
            )) or 0
            completed_count = db.scalar(select(func.count(Ticket.id)).where(
                Ticket.counter_id == counter.id,
                Ticket.status == TicketStatus.COMPLETED,
            )) or 0
            capacity = min(((completed_count + 1) * 15) + (waiting_count * 25), 100)
            counter_stats.append({"name": counter.name, "waiting": waiting_count, "completed": completed_count, "capacity": capacity, "paused": counter.is_paused})

        return render_template(
            "manager.html",
            kpis=kpis,
            peak_hours=peak_hours,
            peak_hour_bars=peak_hour_bars,
            start=start_date.date().isoformat(),
            end=end_date.date().isoformat(),
            weather=weather,
            coach=coach,
            trend_points=trend_points,
            status_mix=status_mix,
            status_gradient=status_gradient,
            department_mix=department_mix,
            counter_stats=counter_stats,
        )


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(full_name) < 2:
            flash("Please enter your full name.", "danger")
        elif len(username) < 3:
            flash("Username must be at least 3 characters.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        else:
            with get_session() as db:
                existing = db.scalar(select(User).where(User.username == username))
                if existing:
                    flash("That username is already registered.", "danger")
                else:
                    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                    user = User(
                        full_name=full_name,
                        username=username,
                        password_hash=password_hash,
                        role=Role.CUSTOMER,
                        is_active=True,
                    )
                    db.add(user)
                    db.flush()
                    session["user_id"] = user.id
                    session["user_name"] = user.full_name
                    session["user_role"] = user.role.value
                    flash("Account created successfully.", "success")
                    return redirect(url_for("customer_portal"))

    return render_template("register.html")


@app.get("/arena")
@login_required
@roles_required(Role.ADMIN, Role.MANAGER)
def queue_arena():
    scenario = request.args.get("scenario", "normal")
    incoming = {"normal": 6, "busy": 18, "surge": 36}.get(scenario, 6)

    with get_session() as db:
        waiting_count = db.scalar(select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.WAITING)) or 0
        active_counters = db.scalar(select(func.count(Counter.id)).where(Counter.is_active.is_(True), Counter.is_paused.is_(False))) or 0
        average_wait = db.scalar(select(func.avg(Ticket.estimated_wait_minutes)).where(Ticket.status == TicketStatus.WAITING))

        projected_queue = waiting_count + incoming
        projected_wait = int(round(projected_queue * max(float(average_wait or 8), 4) / max(active_counters, 1)))
        queue_weather_live = WaitPredictor(db).queue_weather()

    return render_template(
        "arena.html",
        scenario=scenario,
        incoming=incoming,
        waiting_count=waiting_count,
        active_counters=active_counters,
        projected_queue=projected_queue,
        projected_wait=projected_wait,
        weather=queue_weather_live,
    )


@app.post("/arena/simulate")
@login_required
@roles_required(Role.ADMIN, Role.MANAGER)
def simulate_queue_arena():
    payload = request.get_json(silent=True) or request.form

    scenario = str(payload.get("scenario", request.args.get("scenario", "normal"))).lower()
    try:
        incoming = max(0, min(int(payload.get("incoming", {"normal": 6, "busy": 18, "surge": 36}.get(scenario, 6))), 100))
    except (TypeError, ValueError):
        incoming = 6
    try:
        simulated_counters = max(1, min(int(payload.get("active_counters", 1)), 20))
    except (TypeError, ValueError):
        simulated_counters = 1
    try:
        service_speed = max(50, min(int(payload.get("service_speed", 100)), 150))
    except (TypeError, ValueError):
        service_speed = 100

    with get_session() as db:
        waiting_count = db.scalar(select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.WAITING)) or 0
        live_active_counters = db.scalar(select(func.count(Counter.id)).where(Counter.is_active.is_(True), Counter.is_paused.is_(False))) or 0
        average_wait = db.scalar(select(func.avg(Ticket.estimated_wait_minutes)).where(Ticket.status == TicketStatus.WAITING))

        avg_wait = max(float(average_wait or 8), 4)
        projected_queue = waiting_count + incoming
        projected_wait = int(round(projected_queue * avg_wait * (100 / service_speed) / max(simulated_counters, 1)))

        workload = projected_queue / max(simulated_counters, 1)
        if workload <= 3:
            weather = "CALM"
        elif workload <= 8:
            weather = "BUSY"
        else:
            weather = "CRITICAL"

        capacity_delta = simulated_counters - live_active_counters
        if capacity_delta > 0:
            recommendation = f"Model opens {capacity_delta} additional counter{'s' if capacity_delta != 1 else ''}."
        elif capacity_delta < 0:
            recommendation = f"Model closes {abs(capacity_delta)} active counter{'s' if abs(capacity_delta) != 1 else ''}."
        else:
            recommendation = "Model keeps the current counter capacity."

        if projected_wait < 20:
            action = "Capacity appears comfortable for this scenario."
        elif projected_wait < 45:
            action = "Prepare one additional counter if the surge arrives."
        else:
            action = "High pressure detected. Activate extra coverage immediately."

    return {"arena": {
        "scenario": scenario,
        "incoming": incoming,
        "waiting": waiting_count,
        "live_active_counters": live_active_counters,
        "active_counters": simulated_counters,
        "service_speed": service_speed,
        "projected_queue": projected_queue,
        "projected_wait": projected_wait,
        "weather": weather,
        "recommendation": recommendation,
        "action": action,
    }}


DATABASE_TABLES = {
    "users": (User, "Users"),
    "departments": (Department, "Departments"),
    "services": (Service, "Services"),
    "counters": (Counter, "Counters"),
    "tickets": (Ticket, "Tickets"),
    "ticket_events": (TicketEvent, "Ticket Events"),
    "customer_feedback": (CustomerFeedback, "Customer Feedback"),
    "settings": (Setting, "Settings"),
    "queue_metrics": (QueueMetric, "Queue Metrics"),
}


def _serialize_db_value(value):
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if value is None:
        return "—"
    return str(value)


@app.get("/database")
@login_required
@roles_required(Role.ADMIN, Role.MANAGER)
def database_panel():
    table_name = request.args.get("table", "tickets").strip().lower()
    if table_name not in DATABASE_TABLES:
        table_name = "tickets"
    query_text = request.args.get("q", "").strip()

    model, label = DATABASE_TABLES[table_name]
    columns = [column for column in model.__table__.columns if column.key != "password_hash"]

    with get_session() as db:
        counts = {
            name: db.scalar(select(func.count()).select_from(model_class)) or 0
            for name, (model_class, _label) in DATABASE_TABLES.items()
        }

        stmt = select(model).order_by(desc(model.id)).limit(100)
        if query_text:
            search_columns = [column for column in model.__table__.columns if getattr(column.type, "python_type", None) is str]
            if "password_hash" in [column.key for column in search_columns]:
                search_columns = [column for column in search_columns if column.key != "password_hash"]
            if search_columns:
                stmt = stmt.where(or_(*[column.ilike(f"%{query_text}%") for column in search_columns]))

        records = list(db.scalars(stmt).all())
        rows = []
        for record in records:
            row = {column.key: _serialize_db_value(getattr(record, column.key)) for column in columns}
            row["id"] = record.id
            rows.append(row)

        return render_template(
            "database.html",
            table_name=table_name,
            table_label=label,
            table_names=DATABASE_TABLES,
            counts=counts,
            columns=[column.key for column in columns],
            rows=rows,
            query_text=query_text,
            db_path=str(DB_PATH),
        )


@app.get("/database/export/<table_name>")
@login_required
@roles_required(Role.ADMIN, Role.MANAGER)
def export_database_table(table_name):
    if table_name not in DATABASE_TABLES:
        flash("Unknown database table.", "danger")
        return redirect(url_for("database_panel"))

    model, label = DATABASE_TABLES[table_name]
    columns = [column for column in model.__table__.columns if column.key != "password_hash"]

    with get_session() as db:
        records = list(db.scalars(select(model).order_by(desc(model.id)).limit(1000)).all())
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([column.key for column in columns])
        for record in records:
            writer.writerow([_serialize_db_value(getattr(record, column.key)) for column in columns])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table_name}.csv"},
    )


@app.post("/database/action")
@login_required
@roles_required(Role.ADMIN, Role.MANAGER)
def database_action():
    table_name = request.form.get("table", "")
    record_id = request.form.get("record_id", type=int)
    action = request.form.get("action", "")

    if table_name not in DATABASE_TABLES or not record_id:
        flash("Invalid database action.", "danger")
        return redirect(url_for("database_panel", table=table_name or "tickets"))

    model, _label = DATABASE_TABLES[table_name]

    with get_session() as db:
        record = db.get(model, record_id)
        if not record:
            flash("Record not found.", "danger")
            return redirect(url_for("database_panel", table=table_name))

        if table_name == "tickets":
            if action == "cancel":
                record.status = TicketStatus.CANCELLED
                db.flush()
                db.add(TicketEvent(ticket_id=record.id, event_type="CANCELLED", note="Cancelled from Database Panel", performed_by_user_id=session.get("user_id")))
                flash("Ticket cancelled.", "warning")
            elif action == "delete":
                db.query(TicketEvent).filter(TicketEvent.ticket_id == record.id).delete(synchronize_session=False)
                db.query(CustomerFeedback).filter(CustomerFeedback.ticket_id == record.id).delete(synchronize_session=False)
                db.delete(record)
                flash("Ticket deleted.", "warning")
            else:
                flash("Unknown ticket action.", "danger")

        elif table_name == "users":
            if record.id == session.get("user_id"):
                flash("You cannot deactivate your own account.", "danger")
            elif action == "toggle_active":
                record.is_active = not record.is_active
                flash("User status updated.", "success")
            elif action == "delete":
                flash("User deletion is disabled for account safety.", "danger")

        elif table_name == "counters":
            if action == "pause":
                record.is_paused = True
                flash("Counter paused.", "warning")
            elif action == "resume":
                record.is_paused = False
                flash("Counter resumed.", "success")
            elif action == "toggle_active":
                record.is_active = not record.is_active
                flash("Counter status updated.", "success")

        elif table_name in {"departments", "services"}:
            if action == "toggle_active":
                record.is_active = not record.is_active
                flash("Record status updated.", "success")

        elif table_name in {"customer_feedback", "ticket_events", "settings", "queue_metrics"}:
            if action == "delete":
                db.delete(record)
                flash("Record deleted.", "warning")

        else:
            flash("No safe action is available for this table.", "danger")

    return redirect(url_for("database_panel", table=table_name))


@app.post("/database/reset-operational")
@login_required
@roles_required(Role.ADMIN)
def reset_operational_database():
    confirmation = request.form.get("confirmation", "").strip()
    if confirmation != "CLEAR OPERATIONAL DATA":
        flash("Reset cancelled. Type the exact confirmation text.", "danger")
        return redirect(url_for("database_panel", table="tickets"))

    with get_session() as db:
        db.query(CustomerFeedback).delete(synchronize_session=False)
        db.query(TicketEvent).delete(synchronize_session=False)
        db.query(Ticket).delete(synchronize_session=False)
        db.query(QueueMetric).delete(synchronize_session=False)

    flash("Operational ticket data cleared. Departments, services, counters, and users were preserved.", "warning")
    return redirect(url_for("database_panel", table="tickets"))


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
