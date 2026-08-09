"""
Optional email alert for severity>=4 SIGACTs. Fully optional — if
ALERT_SMTP_HOST/ALERT_EMAIL_TO aren't set in .env, this silently does
nothing. Uses stdlib smtplib only, no extra dependency.
"""
import logging
import smtplib
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger("sentinel.alerts")

ALERT_SEVERITY_THRESHOLD = 4


def alerts_enabled() -> bool:
    return bool(settings.ALERT_SMTP_HOST and settings.ALERT_EMAIL_TO)


def send_alert_email(article) -> bool:
    if not alerts_enabled():
        return False

    subject = f"[SENTINEL] Sev {article.severity} {article.category} — {article.ao}"
    body = (
        f"{article.title}\n\n"
        f"AO: {article.ao}\nCategory: {article.category}\nCountry: {article.country}\n"
        f"Published: {article.published_at}\n\nSource: {article.url}\n\n"
        f"{(article.summary or '')[:500]}"
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.ALERT_EMAIL_FROM or settings.ALERT_SMTP_USER
    msg["To"] = settings.ALERT_EMAIL_TO

    try:
        with smtplib.SMTP(settings.ALERT_SMTP_HOST, settings.ALERT_SMTP_PORT, timeout=15) as server:
            server.starttls()
            if settings.ALERT_SMTP_USER:
                server.login(settings.ALERT_SMTP_USER, settings.ALERT_SMTP_PASS)
            server.sendmail(msg["From"], [settings.ALERT_EMAIL_TO], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Alert email failed: %s", exc)
        return False
