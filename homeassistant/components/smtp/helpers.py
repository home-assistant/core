"""Helper utilities for the smtp integration."""

from __future__ import annotations

import smtplib
import socket

from homeassistant.util.ssl import client_context


def try_connect(
    server: str,
    port: int,
    timeout: int,
    encryption: str,
    username: str | None,
    password: str | None,
    verify_ssl: bool,
) -> str | None:
    """Try to connect to the SMTP server and return error key if failed."""
    ssl_context = client_context() if verify_ssl else None
    mail: smtplib.SMTP_SSL | smtplib.SMTP | None = None

    try:
        if encryption == "tls":
            mail = smtplib.SMTP_SSL(
                server,
                port,
                timeout=timeout,
                context=ssl_context,
            )
        else:
            mail = smtplib.SMTP(server, port, timeout=timeout)

        mail.ehlo_or_helo_if_needed()

        if encryption == "starttls":
            mail.starttls(context=ssl_context)
            mail.ehlo()

        if username and password:
            mail.login(username, password)

        return None

    except (socket.gaierror, ConnectionRefusedError, TimeoutError, OSError):
        return "cannot_connect"
    except smtplib.SMTPAuthenticationError:
        return "invalid_auth"
    except smtplib.SMTPException:
        return "cannot_connect"
    finally:
        if mail:
            try:
                mail.quit()
            except smtplib.SMTPException:
                pass
