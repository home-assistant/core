"""Helpers for SMTP integration."""

from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import os
from pathlib import Path
import smtplib
import socket
import ssl

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .const import ATTR_HTML, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SmtpClient:
    """Mailer class."""

    def __init__(
        self,
        server: str,
        port: int,
        timeout: int,
        sender: str,
        encryption: str,
        username: str | None,
        password: str | None,
        sender_name: str | None,
        verify_ssl: bool,
        ssl_context: ssl.SSLContext | None,
    ) -> None:
        """Initialize the SMTP service."""
        self._server = server
        self._port = port
        self._timeout = timeout
        self._sender = sender
        self.encryption = encryption
        self.username = username
        self.password = password
        self._sender_name = sender_name
        self._verify_ssl = verify_ssl
        self.tries = 2
        self._ssl_context = ssl_context

    def connect(self) -> smtplib.SMTP_SSL | smtplib.SMTP:
        """Connect/authenticate to SMTP Server."""
        mail: smtplib.SMTP_SSL | smtplib.SMTP
        if self.encryption == "tls":
            mail = smtplib.SMTP_SSL(
                self._server,
                self._port,
                timeout=self._timeout,
                context=self._ssl_context,
            )
        else:
            mail = smtplib.SMTP(self._server, self._port, timeout=self._timeout)
        mail.ehlo_or_helo_if_needed()
        if self.encryption == "starttls":
            mail.starttls(context=self._ssl_context)
            mail.ehlo()
        if self.username and self.password:
            mail.login(self.username, self.password)
        return mail

    def connection_is_valid(self) -> bool:
        """Check for valid config, verify connectivity."""
        server = None
        try:
            server = self.connect()
        except socket.gaierror, ConnectionRefusedError:
            _LOGGER.exception(
                (
                    "SMTP server not found or refused connection (%s:%s). Please check"
                    " the IP address, hostname, and availability of your SMTP server"
                ),
                self._server,
                self._port,
            )

        except smtplib.SMTPAuthenticationError:
            _LOGGER.exception(
                "Login not possible. Please check your setting and/or your credentials"
            )
            return False

        finally:
            if server:
                server.quit()

        return True


def _build_text_msg(message: str) -> MIMEText:
    """Build plaintext email."""
    _LOGGER.debug("Building plain text email")
    return MIMEText(message)


def _attach_file(
    hass: HomeAssistant, atch_name: str, content_id: str | None = None
) -> MIMEImage | MIMEApplication | None:
    """Create a message attachment.

    If MIMEImage is successful and content_id is passed (HTML), add images in-line.
    Otherwise add them as attachments.
    """
    try:
        file_path = Path(atch_name).parent
        if os.path.exists(file_path) and not hass.config.is_allowed_path(
            str(file_path)
        ):
            allow_list = "allowlist_external_dirs"
            file_name = os.path.basename(atch_name)
            url = "https://www.home-assistant.io/docs/configuration/basic/"
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="remote_path_not_allowed",
                translation_placeholders={
                    "allow_list": allow_list,
                    "file_path": str(file_path),
                    "file_name": file_name,
                    "url": url,
                },
            )
        with open(atch_name, "rb") as attachment_file:
            file_bytes = attachment_file.read()
    except FileNotFoundError:
        _LOGGER.warning("Attachment %s not found. Skipping", atch_name)
        return None

    attachment: MIMEImage | MIMEApplication
    try:
        attachment = MIMEImage(file_bytes)
    except TypeError:
        _LOGGER.warning(
            "Attachment %s has an unknown MIME type. Falling back to file",
            atch_name,
        )
        attachment = MIMEApplication(file_bytes, Name=os.path.basename(atch_name))
        attachment["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(atch_name)}"'
        )
    else:
        if content_id:
            attachment.add_header("Content-ID", f"<{content_id}>")
        else:
            attachment.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(atch_name)}",
            )

    return attachment


def _build_multipart_msg(
    hass: HomeAssistant, message: str, images: list[str]
) -> MIMEMultipart:
    """Build Multipart message with images as attachments."""
    _LOGGER.debug("Building multipart email with image attachment(s)")
    msg = MIMEMultipart()
    body_txt = MIMEText(message)
    msg.attach(body_txt)

    for atch_name in images:
        attachment = _attach_file(hass, atch_name)
        if attachment:
            msg.attach(attachment)

    return msg


def _build_html_msg(
    hass: HomeAssistant, text: str, html: str, images: list[str]
) -> MIMEMultipart:
    """Build Multipart message with in-line images and rich HTML (UTF-8)."""
    _LOGGER.debug("Building HTML rich email")
    msg = MIMEMultipart("related")
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(text, _charset="utf-8"))
    alternative.attach(MIMEText(html, ATTR_HTML, _charset="utf-8"))
    msg.attach(alternative)

    for atch_name in images:
        name = os.path.basename(atch_name)
        attachment = _attach_file(hass, atch_name, name)
        if attachment:
            msg.attach(attachment)
    return msg
