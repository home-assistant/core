"""Mail (SMTP) notification service."""
from __future__ import annotations

from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email.utils
import logging
import os
import smtplib
from typing import Any

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from . import get_smtp_client
from .config_flow import RECEPIENTS_SCHEMA
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

_LOGGER = logging.getLogger(__name__)


# pylint: disable=no-value-for-parameter
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MailNotificationService | None:
    """Get the mail notification service."""
    if discovery_info is None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config
            )
        )
        return None

    return MailNotificationService(discovery_info)


class MailNotificationService(BaseNotificationService):
    """Implement the notification service for E-mail messages."""

    def __init__(self, entry: dict[str, Any]) -> None:
        """Initialize the SMTP service."""
        self.entry = entry

    def send_message(self, message: str, **kwargs: dict[str, Any]) -> None:
        """
        Build and send a message to a user.

        Will send plain text normally, or will build a multipart HTML message
        with inline image attachments if images config is defined, or will
        build a multipart HTML if html config is defined.
        """
        subject = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        if data := kwargs.get(ATTR_DATA):
            if ATTR_HTML in data:
                msg: MIMEMultipart | MIMEText = _build_html_msg(
                    message, data[ATTR_HTML], images=data.get(ATTR_IMAGES, [])
                )
            else:
                msg = _build_multipart_msg(message, images=data.get(ATTR_IMAGES, []))
        else:
            msg = _build_text_msg(message)

        msg["Subject"] = subject

        try:
            recipients = RECEPIENTS_SCHEMA(
                kwargs.get(ATTR_TARGET) or self.entry[CONF_RECIPIENT]
            )
        except vol.Invalid:
            _LOGGER.error("Target is not a valid list of email addresses")
            return

        msg["To"] = ",".join(recipients)

        if CONF_SENDER_NAME in self.entry:
            msg["From"] = f"{self.entry[CONF_SENDER_NAME]} <{self.entry[CONF_SENDER]}>"
        else:
            msg["From"] = self.entry[CONF_SENDER]
        msg["X-Mailer"] = "Home Assistant"
        msg["Date"] = email.utils.format_datetime(dt_util.now())
        msg["Message-Id"] = email.utils.make_msgid()

        return self._send_email(msg, recipients)

    def _send_email(self, msg: MIMEMultipart | MIMEText, recipients: list[str]) -> None:
        """Send the message."""
        mail = get_smtp_client(self.entry)
        for _ in range(2):
            try:
                mail.sendmail(self.entry[CONF_SENDER], recipients, msg.as_string())
                break
            except smtplib.SMTPServerDisconnected:
                _LOGGER.warning(
                    "SMTPServerDisconnected sending mail: retrying connection"
                )
                mail.quit()
                mail = get_smtp_client(self.entry)
            except smtplib.SMTPException:
                _LOGGER.warning("SMTPException sending mail: retrying connection")
                mail.quit()
                mail = get_smtp_client(self.entry)
        mail.quit()


def _build_text_msg(message: str) -> MIMEText:
    """Build plaintext eself.mail."""
    _LOGGER.debug("Building plain text email")
    return MIMEText(message)


def _attach_file(atch_name: str, content_id: str) -> MIMEImage | MIMEApplication | None:
    """Create a message attachment."""
    try:
        with open(atch_name, "rb") as attachment_file:
            file_bytes = attachment_file.read()
    except FileNotFoundError:
        _LOGGER.warning("Attachment %s not found. Skipping", atch_name)
        return None

    try:
        attachment: MIMEImage | MIMEApplication = MIMEImage(file_bytes)
    except TypeError:
        _LOGGER.warning(
            "Attachment %s has an unknown MIME type. Falling back to file",
            atch_name,
        )
        attachment = MIMEApplication(file_bytes, Name=atch_name)
        attachment["Content-Disposition"] = f'attachment; filename="{atch_name}"'

    attachment.add_header("Content-ID", f"<{content_id}>")
    return attachment


def _build_multipart_msg(message: str, images: list[str]) -> MIMEMultipart:
    """Build Multipart message with in-line images."""
    _LOGGER.debug("Building multipart email with embedded attachment(s)")
    msg = MIMEMultipart("related")
    msg_alt = MIMEMultipart("alternative")
    msg.attach(msg_alt)
    body_txt = MIMEText(message)
    msg_alt.attach(body_txt)
    body_text = [f"<p>{message}</p><br>"]

    for atch_num, atch_name in enumerate(images):
        cid = f"image{atch_num}"
        body_text.append(f'<img src="cid:{cid}"><br>')
        attachment = _attach_file(atch_name, cid)
        if attachment:
            msg.attach(attachment)

    body_html = MIMEText("".join(body_text), "html")
    msg_alt.attach(body_html)
    return msg


def _build_html_msg(text: str, html: str, images: list[str]) -> MIMEMultipart:
    """Build Multipart message with in-line images and rich HTML (UTF-8)."""
    _LOGGER.debug("Building HTML rich email")
    msg = MIMEMultipart("related")
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(text, _charset="utf-8"))
    alternative.attach(MIMEText(html, ATTR_HTML, _charset="utf-8"))
    msg.attach(alternative)

    for atch_name in images:
        name = os.path.basename(atch_name)
        attachment = _attach_file(atch_name, name)
        if attachment:
            msg.attach(attachment)
    return msg
