"""
Sends real emails via SMTP (works with Gmail, Outlook, or any SMTP provider).
If SMTP isn't configured yet, this quietly no-ops instead of crashing the
request that triggered it - so you can deploy this before setting up email,
and turn it on later just by adding the env vars.
"""
import smtplib
from email.mime.text import MIMEText

from app.config import settings


def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_host or not to_email:
        return  # email not configured yet, or no recipient - silently skip

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [to_email], msg.as_string())
    except Exception as e:
        # Never let a broken email config break the actual API request -
        # just log it so it shows up in Railway's deploy logs.
        print(f"[email] Failed to send to {to_email}: {e}")


def notify_assigned(to_email: str, request_id: int, category: str, branch: str) -> None:
    send_email(
        to_email,
        f"You've been assigned to Request #{request_id}",
        f"You've been assigned to a maintenance request:\n\n"
        f"Request #{request_id}\nCategory: {category}\nBranch: {branch}\n\n"
        f"Log in to Swag Control to view details.",
    )


def notify_finance_decision(to_email: str, request_id: int, status: str) -> None:
    if not to_email:
        return
    send_email(
        to_email,
        f"Request #{request_id} — Finance {status}",
        f"Your maintenance request #{request_id} has been {status} by Finance.\n\n"
        f"Log in to Swag Control to view details.",
    )
