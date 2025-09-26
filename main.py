import atexit
import logging
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Iterable, List, Sequence

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask, render_template
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


db = SQLAlchemy()
mail = Mail()
_scheduler: BackgroundScheduler | None = None


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    maintenance_due = db.Column(db.Date, nullable=False)
    last_notified_at = db.Column(db.DateTime(timezone=True))

    maintenance_events = db.relationship(
        "MaintenanceEvent", back_populates="item", cascade="all, delete-orphan"
    )


class MaintenanceEvent(db.Model):
    __tablename__ = "maintenance_events"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    description = db.Column(db.String(255))
    completed_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    item = db.relationship("Item", back_populates="maintenance_events")


class NotificationLog(db.Model):
    __tablename__ = "notification_logs"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"))
    maintenance_event_id = db.Column(
        db.Integer, db.ForeignKey("maintenance_events.id")
    )
    status = db.Column(db.String(32), nullable=False)
    sent_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    item = db.relationship("Item")
    maintenance_event = db.relationship("MaintenanceEvent")


@dataclass
class ItemDisplay:
    item: Item
    status: str
    last_notified_at: datetime | None


app = Flask(__name__)
app.config.from_mapping(
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///inventory.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAINTENANCE_ALERT_WINDOW_DAYS=int(os.getenv("MAINTENANCE_ALERT_WINDOW_DAYS", 7)),
    MAINTENANCE_COMPLETED_WINDOW_HOURS=int(
        os.getenv("MAINTENANCE_COMPLETED_WINDOW_HOURS", 24)
    ),
    NOTIFICATION_REPEAT_WINDOW_HOURS=int(
        os.getenv("NOTIFICATION_REPEAT_WINDOW_HOURS", 24)
    ),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "localhost"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 25)),
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "false").lower() == "true",
    MAIL_USE_SSL=os.getenv("MAIL_USE_SSL", "false").lower() == "true",
    MAIL_SUPPRESS_SEND=os.getenv("MAIL_SUPPRESS_SEND", "true").lower() == "true",
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", "alerts@example.com"),
    MAINTENANCE_ALERT_RECIPIENTS=os.getenv("MAINTENANCE_ALERT_RECIPIENTS", ""),
    MAINTENANCE_ALERT_HOUR=int(os.getenv("MAINTENANCE_ALERT_HOUR", 8)),
    SCHEDULER_TIMEZONE=os.getenv("SCHEDULER_TIMEZONE", "UTC"),
    ENABLE_SCHEDULER=os.getenv("ENABLE_SCHEDULER", "true").lower() == "true",
)

db.init_app(app)
mail.init_app(app)


def _bootstrap_database() -> None:
    with app.app_context():
        db.create_all()


def _collect_recipients() -> List[str]:
    recipients = [
        email.strip()
        for email in app.config["MAINTENANCE_ALERT_RECIPIENTS"].split(",")
        if email.strip()
    ]
    return recipients


def _filter_items_by_notification(
    items: Sequence[Item], status: str, repeat_window_start: datetime
) -> List[Item]:
    if not items:
        return []

    item_ids = [item.id for item in items]
    recent_logs: Iterable[NotificationLog] = NotificationLog.query.filter(
        NotificationLog.item_id.in_(item_ids),
        NotificationLog.status == status,
        NotificationLog.sent_at >= repeat_window_start,
    ).all()

    already_notified = {log.item_id for log in recent_logs if log.item_id}
    return [item for item in items if item.id not in already_notified]


def _filter_events_by_notification(
    events: Sequence[MaintenanceEvent], repeat_window_start: datetime
) -> List[MaintenanceEvent]:
    if not events:
        return []

    event_ids = [event.id for event in events]
    recent_logs: Iterable[NotificationLog] = NotificationLog.query.filter(
        NotificationLog.maintenance_event_id.in_(event_ids),
        NotificationLog.sent_at >= repeat_window_start,
    ).all()

    already_notified = {
        log.maintenance_event_id
        for log in recent_logs
        if log.maintenance_event_id is not None
    }
    return [event for event in events if event.id not in already_notified]


def _format_item_line(prefix: str, items: Sequence[Item]) -> List[str]:
    lines = []
    for item in items:
        due = item.maintenance_due.isoformat()
        lines.append(f"- {prefix}: {item.name} (due {due})")
    return lines


def _format_event_line(events: Sequence[MaintenanceEvent]) -> List[str]:
    lines = []
    for event in events:
        name = event.item.name if event.item else "Unknown item"
        when = event.completed_at.strftime("%Y-%m-%d %H:%M")
        description = event.description or "Maintenance completed"
        lines.append(f"- Completed: {name} at {when} — {description}")
    return lines


def _build_email_body(
    due_items: Sequence[Item],
    overdue_items: Sequence[Item],
    completed_events: Sequence[MaintenanceEvent],
) -> str:
    lines = ["Daily maintenance summary:"]

    if overdue_items:
        lines.append("")
        lines.append("Overdue items:")
        lines.extend(_format_item_line("Overdue", overdue_items))

    if due_items:
        lines.append("")
        lines.append("Due soon:")
        lines.extend(_format_item_line("Due soon", due_items))

    if completed_events:
        lines.append("")
        lines.append("Recently completed:")
        lines.extend(_format_event_line(completed_events))

    if len(lines) == 1:
        lines.append("\nNo new maintenance updates today.")

    return "\n".join(lines)


def _record_notifications(
    due_items: Sequence[Item],
    overdue_items: Sequence[Item],
    completed_events: Sequence[MaintenanceEvent],
) -> None:
    timestamp = datetime.now(UTC)

    for item in due_items:
        db.session.add(
            NotificationLog(item_id=item.id, status="due", sent_at=timestamp)
        )
        item.last_notified_at = timestamp

    for item in overdue_items:
        db.session.add(
            NotificationLog(item_id=item.id, status="overdue", sent_at=timestamp)
        )
        item.last_notified_at = timestamp

    for event in completed_events:
        db.session.add(
            NotificationLog(
                maintenance_event_id=event.id, status="completed", sent_at=timestamp
            )
        )

    db.session.commit()


def _send_alert_email(
    recipients: Sequence[str],
    due_items: Sequence[Item],
    overdue_items: Sequence[Item],
    completed_events: Sequence[MaintenanceEvent],
) -> bool:
    if not recipients:
        logger.info("No recipients configured for maintenance alerts.")
        return False

    subject = f"Maintenance summary for {date.today().isoformat()}"
    body = _build_email_body(due_items, overdue_items, completed_events)
    message = Message(subject=subject, recipients=list(recipients), body=body)

    try:
        mail.send(message)
        logger.info(
            "Sent maintenance alert email to %s", ", ".join(recipients)
        )
        return True
    except Exception as exc:  # pragma: no cover - log unexpected mail failures
        logger.exception("Unable to send maintenance alert email: %%s", exc)
        return False


def run_notification_cycle() -> None:
    """Scan for maintenance updates and send notifications."""

    with app.app_context():
        today = date.today()
        now = datetime.now(UTC)
        window_days = app.config["MAINTENANCE_ALERT_WINDOW_DAYS"]
        repeat_window_hours = app.config["NOTIFICATION_REPEAT_WINDOW_HOURS"]
        completed_window_hours = app.config["MAINTENANCE_COMPLETED_WINDOW_HOURS"]

        window_start = today
        window_end = today + timedelta(days=window_days)

        due_items = Item.query.filter(
            Item.maintenance_due >= window_start,
            Item.maintenance_due <= window_end,
        ).order_by(Item.maintenance_due.asc()).all()

        overdue_items = Item.query.filter(Item.maintenance_due < window_start).order_by(
            Item.maintenance_due.asc()
        ).all()

        repeat_window_start = now - timedelta(hours=repeat_window_hours)
        due_items = _filter_items_by_notification(
            due_items, "due", repeat_window_start
        )
        overdue_items = _filter_items_by_notification(
            overdue_items, "overdue", repeat_window_start
        )

        completed_since = now - timedelta(hours=completed_window_hours)
        completed_events = (
            MaintenanceEvent.query.filter(
                MaintenanceEvent.completed_at >= completed_since
            )
            .order_by(MaintenanceEvent.completed_at.desc())
            .all()
        )
        completed_events = _filter_events_by_notification(
            completed_events, repeat_window_start
        )

        if not any([due_items, overdue_items, completed_events]):
            logger.info("No maintenance updates to notify about.")
            return

        recipients = _collect_recipients()
        if _send_alert_email(recipients, due_items, overdue_items, completed_events):
            _record_notifications(due_items, overdue_items, completed_events)


def _start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone=app.config["SCHEDULER_TIMEZONE"])
    trigger = CronTrigger(hour=app.config["MAINTENANCE_ALERT_HOUR"], minute=0)
    _scheduler.add_job(run_notification_cycle, trigger=trigger, id="maintenance_scan")
    _scheduler.start()
    atexit.register(lambda: _scheduler.shutdown(wait=False))
    logger.info(
        "Scheduled daily maintenance scan at %s:00", app.config["MAINTENANCE_ALERT_HOUR"]
    )


@app.route("/")
def dashboard():
    today = date.today()
    window_days = app.config["MAINTENANCE_ALERT_WINDOW_DAYS"]
    upcoming_cutoff = today + timedelta(days=window_days)

    items: List[ItemDisplay] = []
    for item in Item.query.order_by(Item.maintenance_due.asc()).all():
        if item.maintenance_due < today:
            status = "Overdue"
        elif item.maintenance_due <= upcoming_cutoff:
            status = "Due soon"
        else:
            status = "On schedule"

        items.append(ItemDisplay(item=item, status=status, last_notified_at=item.last_notified_at))

    recent_notifications = (
        NotificationLog.query.order_by(NotificationLog.sent_at.desc()).limit(20).all()
    )

    return render_template(
        "dashboard.html",
        items=items,
        recent_notifications=recent_notifications,
        today=today,
        window_days=window_days,
    )


_bootstrap_database()
if app.config["ENABLE_SCHEDULER"]:
    _start_scheduler()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inventory tracker service")
    parser.add_argument(
        "--scan-once",
        action="store_true",
        help="Run the maintenance scan once and exit.",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host address for the Flask server"
    )
    parser.add_argument("--port", default=5000, type=int, help="Port for the Flask server")

    args = parser.parse_args()

    if args.scan_once:
        run_notification_cycle()
    else:
        app.run(host=args.host, port=args.port)
