"""Mail (SMTP) notification service."""

from contextlib import suppress
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email.utils
import logging
from smtplib import (
    SMTP,
    SMTP_SSL,
    SMTPAuthenticationError,
    SMTPException,
    SMTPServerDisconnected,
)
from socket import gaierror
from ssl import SSLContext
from typing import TYPE_CHECKING, Any, override

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
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import create_client_context

from . import SmtpConfigEntry
from .const import (
    ATTR_HTML,
    ATTR_IMAGES,
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
from .helpers import SmtpClient, _build_html_msg, _build_multipart_msg, _build_text_msg
from .issue import async_deprecate_yaml_issue

PLATFORMS = [Platform.NOTIFY]

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

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
        if discovery_info[CONF_VERIFY_SSL]
        else None
    )
    mail_service = MailNotificationService(discovery_info, ssl_context)

    if await hass.async_add_executor_job(mail_service.connection_is_valid):
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
        client: SmtpClient,
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
    def send_message(self, message: str, title: str | None = None) -> None:
        """Send an email message via notify.send_message action."""

        msg = MIMEText(message)
        msg["Subject"] = title or ATTR_TITLE_DEFAULT

        self._send_email(msg=msg)

    def _send_email(self, msg: MIMEMultipart | MIMEText) -> None:
        """Send the message."""
        if TYPE_CHECKING:
            assert self._subentry.unique_id

        msg["From"] = email.utils.formataddr(
            (self._entry.data.get(CONF_SENDER_NAME), self._entry.data[CONF_SENDER])
        )
        msg["To"] = email.utils.formataddr(
            (self._subentry.title, self._subentry.unique_id)
        )
        msg["X-Mailer"] = "Home Assistant"
        msg["Date"] = email.utils.format_datetime(dt_util.now())
        msg["Message-Id"] = email.utils.make_msgid()

        client: SMTP_SSL | SMTP | None = None
        for attempt in range(self._client.tries):
            try:
                client = self._client.connect()
            except SMTPAuthenticationError as e:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_error",
                ) from e
            except (gaierror, ConnectionRefusedError, SMTPException) as e:
                _LOGGER.debug("Full exception:", exc_info=True)
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="send_mail_connection_error",
                ) from e

            try:
                client.sendmail(
                    self._entry.data[CONF_SENDER],
                    self._subentry.unique_id,
                    msg.as_string(),
                )
                break
            except SMTPException as e:
                _LOGGER.debug(
                    "Error sending mail at attempt %s:", attempt + 1, exc_info=True
                )
                if attempt == self._client.tries - 1:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="send_mail_connection_error",
                    ) from e
            finally:
                with suppress(SMTPException):
                    client.quit()


class MailNotificationService(SmtpClient, BaseNotificationService):
    """Implement the notification service for E-mail messages."""

    def __init__(
        self,
        config: DiscoveryInfoType,
        ssl_context: SSLContext | None,
    ) -> None:
        """Initialize the SMTP service."""
        self.recipients = config[CONF_RECIPIENT]
        super().__init__(
            server=config[CONF_SERVER],
            port=config[CONF_PORT],
            timeout=config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            sender=config[CONF_SENDER],
            encryption=config[CONF_ENCRYPTION],
            username=config.get(CONF_USERNAME),
            password=config.get(CONF_PASSWORD),
            sender_name=config.get(CONF_SENDER_NAME),
            verify_ssl=config[CONF_VERIFY_SSL],
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
