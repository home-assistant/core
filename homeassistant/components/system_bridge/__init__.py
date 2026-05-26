"""The System Bridge integration."""

import asyncio
import logging

from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
    DataMissingException,
)
from systembridgeconnector.version import Version

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .config_flow import SystemBridgeConfigFlow
from .const import DATA_WAIT_TIMEOUT, DOMAIN, MODULES
from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.UPDATE,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the System Bridge services."""

    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
) -> bool:
    """Set up System Bridge from a config entry."""

    # Check version before initialising
    version = Version(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
        session=async_get_clientsession(hass),
    )
    supported = False
    try:
        async with asyncio.timeout(DATA_WAIT_TIMEOUT):
            supported = await version.check_supported()
    except AuthenticationException as exception:
        _LOGGER.error("Authentication failed for %s: %s", entry.title, exception)
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_failed",
            translation_placeholders={
                "title": entry.title,
                "host": entry.data[CONF_HOST],
            },
        ) from exception
    except (ConnectionClosedException, ConnectionErrorException) as exception:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={
                "title": entry.title,
                "host": entry.data[CONF_HOST],
            },
        ) from exception
    except TimeoutError as exception:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="timeout",
            translation_placeholders={
                "title": entry.title,
                "host": entry.data[CONF_HOST],
            },
        ) from exception

    # If not supported, create an issue and raise ConfigEntryNotReady
    if not supported:
        async_create_issue(
            hass=hass,
            domain=DOMAIN,
            issue_id=f"system_bridge_{entry.entry_id}_unsupported_version",
            translation_key="unsupported_version",
            translation_placeholders={"host": entry.data[CONF_HOST]},
            severity=IssueSeverity.ERROR,
            is_fixable=False,
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="unsupported_version",
            translation_placeholders={
                "title": entry.title,
                "host": entry.data[CONF_HOST],
            },
        )

    coordinator = SystemBridgeDataUpdateCoordinator(
        hass,
        _LOGGER,
        entry=entry,
    )

    try:
        async with asyncio.timeout(DATA_WAIT_TIMEOUT):
            await coordinator.async_get_data(MODULES)
    except AuthenticationException as exception:
        _LOGGER.error("Authentication failed for %s: %s", entry.title, exception)
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="authentication_failed",
            translation_placeholders={
                "title": entry.title,
                "host": entry.data[CONF_HOST],
            },
        ) from exception
    except (ConnectionClosedException, ConnectionErrorException) as exception:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={
                "title": entry.title,
                "host": entry.data[CONF_HOST],
            },
        ) from exception
    except (DataMissingException, TimeoutError) as exception:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="timeout",
            translation_placeholders={
                "title": entry.title,
                "host": entry.data[CONF_HOST],
            },
        ) from exception

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up legacy notify platform
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_NAME: f"{DOMAIN}_{coordinator.data.system.hostname}",
                CONF_ENTITY_ID: entry.entry_id,
            },
            {},
        )
    )

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SystemBridgeConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data

        # Ensure disconnected and cleanup stop sub
        await coordinator.websocket_client.close()
        if coordinator.unsub:
            coordinator.unsub()

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant, entry: SystemBridgeConfigEntry
) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > SystemBridgeConfigFlow.VERSION:
        return False

    if config_entry.minor_version < 2:
        # Migrate to CONF_TOKEN, which was added in 1.2
        new_data = dict(config_entry.data)
        new_data.setdefault(CONF_TOKEN, config_entry.data.get(CONF_API_KEY))

        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            minor_version=2,
        )

        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

    return True
