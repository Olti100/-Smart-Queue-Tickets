from __future__ import annotations

from datetime import datetime, timedelta
from functools import wraps
from os import getenv

import bcrypt
from flask import Flask, flash, redirect, render_template, request, session, url_for
from sqlalchemy import desc, or_, select

from core.analytics_engine import AnalyticsEngine
from core.queue_engine import QueueEngine
from database.bootstrap import bootstrap_database
from database.connection import get_session
from database.models import (
    Counter,
    CustomerFeedback,
    Department,
    PriorityCategory,
    Role,
    Service,
    Ticket,
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
        stmt = select(Ticket).order_by(desc(Ticket.created_at)).limit(60)
        if query:
            stmt = stmt.where(
                or_(
                    Ticket.ticket_number.ilike(f"%{query}%"),
                    Ticket.customer_name.ilike(f"%{query}%"),
                )
            )
        tickets = list(db.scalars(stmt).all())

        return render_template(
            "receptionist.html",
            tickets=tickets,
            departments=departments,
            services=services,
            priorities=[p.value for p in PriorityCategory],
            query=query,
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

        return render_template(
            "staff.html",
            counters=counters,
            selected_counter=selected_counter,
            current_ticket=current_ticket,
            waiting=waiting,
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

        return render_template(
            "display.html",
            called=called,
            waiting=waiting,
            departments=departments,
            dep_id=dep_id,
            now=datetime.now(),
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

        return render_template(
            "manager.html",
            kpis=kpis,
            peak_hours=peak_hours,
            start=start_date.date().isoformat(),
            end=end_date.date().isoformat(),
        )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
