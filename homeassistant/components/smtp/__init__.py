"""The smtp integration."""

import logging

from aiosmtplib import SMTP, SMTPAuthenticationError, SMTPException

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    discovery,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.ssl import client_context, client_context_no_verify

from .const import (
    CONF_ENCRYPTION,
    CONF_ENTRY,
    CONF_OLD_RECIPIENT,
    CONF_SERVER,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

type SmtpConfigEntry = ConfigEntry[SMTP]

PLATFORMS: list[Platform] = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SMTP services."""

    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SmtpConfigEntry) -> bool:
    """Set up SMTP from a config entry."""

    await async_migrate_subentries(hass, entry)

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_NAME: entry.title,
                CONF_RECIPIENT: [
                    subentry.unique_id for subentry in entry.subentries.values()
                ],
                CONF_ENTRY: entry,
            },
            {},
        )
    )

    client = SMTP(
        hostname=entry.data[CONF_SERVER],
        port=entry.data[CONF_PORT],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        use_tls=entry.data[CONF_ENCRYPTION] == "tls",
        start_tls=entry.data[CONF_ENCRYPTION] == "starttls",
        tls_context=(
            client_context()
            if entry.data[CONF_VERIFY_SSL]
            else client_context_no_verify()
        ),
    )
    try:
        async with client:
            pass
    except SMTPAuthenticationError as e:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_error",
        ) from e
    except SMTPException as e:
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


async def async_migrate_subentries(hass: HomeAssistant, entry: SmtpConfigEntry) -> None:
    """Migrate entity unique_id after subentry reconfiguration."""
    for subentry in entry.subentries.values():
        if (
            (old_unique_id := subentry.data.get(CONF_OLD_RECIPIENT)) is not None
            and old_unique_id != subentry.unique_id
            and (
                entity := er.async_get(hass).async_get_entity_id(
                    NOTIFY_DOMAIN, DOMAIN, f"{entry.entry_id}_{old_unique_id}"
                )
            )
        ):
            er.async_get(hass).async_update_entity(
                entity,
                new_unique_id=f"{entry.entry_id}_{subentry.unique_id}",
            )
            hass.config_entries.async_update_subentry(entry, subentry, data={})
