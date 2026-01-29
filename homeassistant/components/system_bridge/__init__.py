"""The System Bridge integration."""

from __future__ import annotations

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
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .config_flow import SystemBridgeConfigFlow
from .const import DATA_WAIT_TIMEOUT, DOMAIN, MODULES
from .coordinator import SystemBridgeDataUpdateCoordinator
from .services import (
    SERVICE_EXECUTE_COMMAND,
    SERVICE_GET_COMMANDS,
    SERVICE_GET_PROCESS_BY_ID,
    SERVICE_GET_PROCESSES_BY_NAME,
    SERVICE_OPEN_PATH,
    SERVICE_OPEN_URL,
    SERVICE_POWER_COMMAND,
    SERVICE_SEND_KEYPRESS,
    SERVICE_SEND_TEXT,
    async_setup_services,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.UPDATE,
]


async def _check_version_support(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Check if System Bridge version is supported."""
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


async def _initialize_coordinator(
    hass: HomeAssistant, entry: ConfigEntry
) -> SystemBridgeDataUpdateCoordinator:
    """Initialize and validate the coordinator."""
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

    await coordinator.async_config_entry_first_refresh()
    return coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up System Bridge from a config entry."""
    await _check_version_support(hass, entry)
    coordinator = await _initialize_coordinator(hass, entry)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_NAME: f"{DOMAIN}_{coordinator.data.system.hostname}",
                CONF_ENTITY_ID: entry.entry_id,
            },
            hass.data[DOMAIN][entry.entry_id],
        )
    )

    async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )
    if unload_ok:
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            entry.entry_id
        ]

        # Ensure disconnected and cleanup stop sub
        await coordinator.websocket_client.close()
        if coordinator.unsub:
            coordinator.unsub()

        del hass.data[DOMAIN][entry.entry_id]

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, SERVICE_EXECUTE_COMMAND)
        hass.services.async_remove(DOMAIN, SERVICE_GET_COMMANDS)
        hass.services.async_remove(DOMAIN, SERVICE_GET_PROCESS_BY_ID)
        hass.services.async_remove(DOMAIN, SERVICE_GET_PROCESSES_BY_NAME)
        hass.services.async_remove(DOMAIN, SERVICE_OPEN_PATH)
        hass.services.async_remove(DOMAIN, SERVICE_POWER_COMMAND)
        hass.services.async_remove(DOMAIN, SERVICE_OPEN_URL)
        hass.services.async_remove(DOMAIN, SERVICE_SEND_KEYPRESS)
        hass.services.async_remove(DOMAIN, SERVICE_SEND_TEXT)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
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
