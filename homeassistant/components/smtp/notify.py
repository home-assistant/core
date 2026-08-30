"""Mail (SMTP) notification service."""

import asyncio
from contextlib import suppress
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email.utils
import logging
from smtplib import SMTPException, SMTPServerDisconnected
from ssl import SSLContext
from typing import TYPE_CHECKING, Any, override

import aiosmtplib
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigSubentry
from homeassistant.const import (
    CONF_DEBUG,
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
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import create_client_context

from . import SmtpConfigEntry
from .const import (
    ATTR_ATTACHMENTS,
    ATTR_CONTENT_ID,
    ATTR_FILENAME,
    ATTR_HTML,
    ATTR_IMAGES,
    ATTR_MEDIA_SOURCE,
    ATTR_PRIORITY,
    CONF_ENCRYPTION,
    CONF_ENTRY,
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
from .helpers import (
    SmtpClient,
    _build_html_msg,
    _build_multipart_msg,
    _build_text_msg,
    _resolve_media,
)
from .issue import async_deprecate_yaml_issue, deprecated_notify_action_call

PLATFORMS = [Platform.NOTIFY]

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

RETRIES = 2

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

MAP_X_PRIORITY = {
    "highest": "1 (Highest)",
    "high": "2 (High)",
    "normal": "3 (Normal)",
    "low": "4 (Low)",
    "lowest": "5 (Lowest)",
}


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MailNotificationService | None:
    """Get the mail notification service."""
    if config:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        if result.get("type") is FlowResultType.CREATE_ENTRY or (
            result.get("type") is FlowResultType.ABORT
            and result.get("reason") == "already_configured"
        ):
            async_deprecate_yaml_issue(hass, config)
        else:
            async_deprecate_yaml_issue(hass, config, import_success=False)
        return None

    if discovery_info is None:
        return None

    ssl_context = (
        await hass.async_add_executor_job(create_client_context)
        if discovery_info[CONF_ENTRY].data[CONF_VERIFY_SSL]
        else None
    )
    mail_service = MailNotificationService(discovery_info, ssl_context)

    entry: SmtpConfigEntry = discovery_info[CONF_ENTRY]

    if await hass.async_add_executor_job(mail_service.connection_is_valid):
        entry.async_on_unload(mail_service.async_unregister_services)
        return mail_service

    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SmtpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the notification entity platform."""
    client = config_entry.runtime_data

    async_add_entities(
        [
            MailNotifyEntity(config_entry, subentry, client)
            for subentry in config_entry.subentries.values()
        ],
    )

    entity_registry = er.async_get(hass)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    current_recipients = {
        subentry.unique_id for subentry in config_entry.subentries.values()
    }
    for entity in entity_entries:
        if (
            entity.unique_id.removeprefix(f"{config_entry.entry_id}_")
            not in current_recipients
        ):
            entity_registry.async_remove(entity.entity_id)


class MailNotifyEntity(NotifyEntity):
    """Representation of an SMTP notify entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "mailto"
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(
        self,
        entry: SmtpConfigEntry,
        subentry: ConfigSubentry,
        client: aiosmtplib.SMTP,
    ) -> None:
        """Initialize the notify entity."""

        self._entry = entry
        self._subentry = subentry
        self._client = client

        self._attr_unique_id = f"{entry.entry_id}_{subentry.unique_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
        )
        self._attr_name = subentry.title

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send an email message via notify.send_message action."""

        msg = EmailMessage()
        msg.set_content(message)
        msg["Subject"] = title or ATTR_TITLE_DEFAULT

        await self._send_email(msg=msg)

    async def smtp_send_message(
        self,
        message: str,
        title: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Send an email message via smtp.send_message action."""
        msg = EmailMessage()
        msg.set_content(message)
        msg.add_header("Subject", title or ATTR_TITLE_DEFAULT)

        if ATTR_PRIORITY in kwargs:
            msg.add_header("X-Priority", MAP_X_PRIORITY[kwargs[ATTR_PRIORITY]])

        if ATTR_HTML in kwargs:
            msg.add_alternative(kwargs[ATTR_HTML], subtype="html")

        attachments = kwargs.get(ATTR_ATTACHMENTS, [])

        resolved = await asyncio.gather(
            *(
                _resolve_media(self.hass, file[ATTR_MEDIA_SOURCE])
                for file in attachments
            )
        )

        for file, (content, mime_type, filename) in zip(
            attachments, resolved, strict=True
        ):
            main_type, subtype = (
                mime_type.split("/", 1)
                if mime_type is not None and "/" in mime_type
                else ("application", "octet-stream")
            )

            if not (target_filename := file.get(ATTR_FILENAME, filename)):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="media_source_missing_filename",
                    translation_placeholders={
                        "media_content_id": file[ATTR_MEDIA_SOURCE]["media_content_id"]
                    },
                )
            if (html_part := msg.get_body(("related", "html"))) and (
                cid := file.get(ATTR_CONTENT_ID)
            ):
                html_part.add_related(
                    content,
                    maintype=main_type,
                    subtype=subtype,
                    filename=target_filename,
                    cid=f"<{cid}>",
                    disposition="inline",
                )
            else:
                msg.add_attachment(
                    content,
                    maintype=main_type,
                    subtype=subtype,
                    filename=target_filename,
                )

        await self._send_email(msg)
        self._async_record_notification()

    async def _send_email(self, msg: EmailMessage) -> None:
        """Send the message."""
        if TYPE_CHECKING:
            assert self._subentry.unique_id

        msg.add_header(
            "From",
            email.utils.formataddr(
                (self._entry.data.get(CONF_SENDER_NAME), self._entry.data[CONF_SENDER])
            ),
        )
        msg.add_header(
            "To",
            email.utils.formataddr((self._subentry.title, self._subentry.unique_id)),
        )
        msg.add_header("X-Mailer", "Home Assistant")
        msg.add_header("Date", email.utils.format_datetime(dt_util.now()))
        msg.add_header("Message-Id", email.utils.make_msgid())

        for attempt in range(RETRIES):
            try:
                async with self._client as client:
                    await client.send_message(msg)
                break
            except aiosmtplib.SMTPAuthenticationError as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_error",
                ) from e
            except aiosmtplib.SMTPException as e:
                _LOGGER.debug(
                    "Error sending mail at attempt %s:", attempt + 1, exc_info=True
                )
                if attempt == RETRIES - 1:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="send_mail_connection_error",
                    ) from e


class MailNotificationService(SmtpClient, BaseNotificationService):
    """Implement the notification service for E-mail messages."""

    def __init__(
        self,
        config: DiscoveryInfoType,
        ssl_context: SSLContext | None,
    ) -> None:
        """Initialize the SMTP service."""
        self.recipients = config[CONF_RECIPIENT]
        entry: SmtpConfigEntry = config[CONF_ENTRY]

        super().__init__(
            server=entry.data[CONF_SERVER],
            port=entry.data[CONF_PORT],
            timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            sender=entry.data[CONF_SENDER],
            encryption=entry.data[CONF_ENCRYPTION],
            username=entry.data.get(CONF_USERNAME),
            password=entry.data.get(CONF_PASSWORD),
            sender_name=entry.data.get(CONF_SENDER_NAME),
            verify_ssl=entry.data[CONF_VERIFY_SSL],
            ssl_context=ssl_context,
        )

    @override
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
        deprecated_notify_action_call(self.hass, self._service_name)

        mail = self.connect()
        for attempt in range(self.tries):
            try:
                mail.sendmail(self._sender, recipients, msg.as_string())
                break
            except SMTPServerDisconnected as e:
                with suppress(SMTPException):
                    mail.quit()
                if attempt == self.tries - 1:
                    _LOGGER.debug("Full exception:", exc_info=True)
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="send_mail_connection_error",
                    ) from e
                _LOGGER.warning(
                    "SMTPServerDisconnected sending mail: retrying connection",
                    exc_info=_LOGGER.isEnabledFor(logging.DEBUG),
                )
                mail = self.connect()
            except SMTPException as e:
                with suppress(SMTPException):
                    mail.quit()
                if attempt == self.tries - 1:
                    _LOGGER.debug("Full exception:", exc_info=True)
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="send_mail_connection_error",
                    ) from e
                _LOGGER.warning(
                    "SMTPException sending mail: retrying connection",
                    exc_info=_LOGGER.isEnabledFor(logging.DEBUG),
                )
                mail = self.connect()
        with suppress(SMTPException):
            mail.quit()
