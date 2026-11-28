import os
import smtplib
import ssl
from email.message import EmailMessage


def send_verification_code(email: str, code: str) -> None:
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = email
    message["Subject"] = "Код подтверждения регистрации"
    message.set_content(
        f"Ваш код подтверждения: {code}\n"
        "Код действует 10 минут."
    )

    with smtplib.SMTP_SSL(
        os.environ["SMTP_HOST"],
        465,
        timeout=30,
        context=ssl.create_default_context(),
    ) as smtp:
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)