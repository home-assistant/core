"""The smtp integration."""

import logging
from smtplib import SMTPAuthenticationError
from socket import gaierror

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import discovery
from homeassistant.util.ssl import create_client_context

from .const import (
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .helpers import SmtpClient

_LOGGER = logging.getLogger(__name__)

type SmtpConfigEntry = ConfigEntry[SmtpClient]

PLATFORMS: list[Platform] = [Platform.NOTIFY]


async def async_setup_entry(hass: HomeAssistant, entry: SmtpConfigEntry) -> bool:
    """Set up SMTP from a config entry."""

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                **entry.data,
                CONF_NAME: entry.title,
                CONF_RECIPIENT: [
                    subentry.unique_id for subentry in entry.subentries.values()
                ],
                **entry.options,
            },
            {},
        )
    )
    client = SmtpClient(
        server=entry.data[CONF_SERVER],
        port=entry.data[CONF_PORT],
        timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        sender=entry.data[CONF_SENDER],
        encryption=entry.data[CONF_ENCRYPTION],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        sender_name=entry.data.get(CONF_SENDER_NAME),
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        ssl_context=(
            await hass.async_add_executor_job(create_client_context)
            if entry.data[CONF_VERIFY_SSL]
            else None
        ),
    )
    try:
        await hass.async_add_executor_job(lambda: client.connect().quit())
    except SMTPAuthenticationError as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        ) from e
    except (gaierror, ConnectionRefusedError) as e:
        _LOGGER.debug("Full exception:", exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from e

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: SmtpConfigEntry) -> None:
    """Handle update."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SmtpConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
