"""Mail (SMTP) notification service."""

from __future__ import annotations

from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email.utils
import logging
import os
from pathlib import Path
import smtplib
import socket
import ssl
from typing import Any

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.reload import setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import create_client_context

from .const import (
    ATTR_HTML,
    ATTR_IMAGES,
    CONF_DEBUG,
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DEFAULT_DEBUG,
    DEFAULT_ENCRYPTION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ENCRYPTION_OPTIONS,
)

PLATFORMS = [Platform.NOTIFY]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RECIPIENT): vol.All(cv.ensure_list, [vol.Email()]),
        vol.Required(CONF_SENDER): vol.Email(),
        vol.Optional(CONF_SERVER, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_ENCRYPTION, default=DEFAULT_ENCRYPTION): vol.In(
            ENCRYPTION_OPTIONS
        ),
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SENDER_NAME): cv.string,
        vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MailNotificationService | None:
    """Get the mail notification service."""
    setup_reload_service(hass, DOMAIN, PLATFORMS)
    ssl_context = create_client_context() if config[CONF_VERIFY_SSL] else None
    mail_service = MailNotificationService(
        config[CONF_SERVER],
        config[CONF_PORT],
        config[CONF_TIMEOUT],
        config[CONF_SENDER],
        config[CONF_ENCRYPTION],
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config[CONF_RECIPIENT],
        config.get(CONF_SENDER_NAME),
        config[CONF_DEBUG],
        config[CONF_VERIFY_SSL],
        ssl_context,
    )

    if mail_service.connection_is_valid():
        return mail_service

    return None


class MailNotificationService(BaseNotificationService):
    """Implement the notification service for E-mail messages."""

    def __init__(
        self,
        server: str,
        port: int,
        timeout: int,
        sender: str,
        encryption: str,
        username: str | None,
        password: str | None,
        recipients: list[str],
        sender_name: str | None,
        debug: bool,
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
        self.recipients = recipients
        self._sender_name = sender_name
        self.debug = debug
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
        mail.set_debuglevel(self.debug)
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
        except (socket.gaierror, ConnectionRefusedError):
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

    def send_message(self, message: str, **kwargs: Any) -> None:
        """Build and send a message to a user.

        Will send plain text normally, with pictures as attachments if images config is
        defined, or will build a multipart HTML if html config is defined.
        """
        subject = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        msg: MIMEMultipart | MIMEText
        if data := kwargs.get(ATTR_DATA):
            if ATTR_HTML in data:
                msg = _build_html_msg(
                    self.hass,
                    message,
                    data[ATTR_HTML],
                    images=data.get(ATTR_IMAGES, []),
                )
            else:
                msg = _build_multipart_msg(
                    self.hass, message, images=data.get(ATTR_IMAGES, [])
                )
        else:
            msg = _build_text_msg(message)

        msg["Subject"] = subject

        if targets := kwargs.get(ATTR_TARGET):
            recipients: list[str] = targets  # ensured by NOTIFY_SERVICE_SCHEMA
        else:
            recipients = self.recipients
        msg["To"] = ",".join(recipients)

        if self._sender_name:
            msg["From"] = f"{self._sender_name} <{self._sender}>"
        else:
            msg["From"] = self._sender

        msg["X-Mailer"] = "Home Assistant"
        msg["Date"] = email.utils.format_datetime(dt_util.now())
        msg["Message-Id"] = email.utils.make_msgid()

        return self._send_email(msg, recipients)

    def _send_email(self, msg: MIMEMultipart | MIMEText, recipients: list[str]) -> None:
        """Send the message."""
        mail = self.connect()
        for _ in range(self.tries):
            try:
                mail.sendmail(self._sender, recipients, msg.as_string())
                break
            except smtplib.SMTPServerDisconnected:
                _LOGGER.warning(
                    "SMTPServerDisconnected sending mail: retrying connection"
                )
                mail.quit()
                mail = self.connect()
            except smtplib.SMTPException:
                _LOGGER.warning("SMTPException sending mail: retrying connection")
                mail.quit()
                mail = self.connect()
        mail.quit()


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
    _LOGGER.debug("Building multipart email with image attachme_build_html_msgnt(s)")
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
