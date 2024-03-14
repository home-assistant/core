"""The System Bridge integration."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import logging
from typing import Any

from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.version import Version
from systembridgemodels.keyboard_key import KeyboardKey
from systembridgemodels.keyboard_text import KeyboardText
from systembridgemodels.modules.processes import Process
from systembridgemodels.open_path import OpenPath
from systembridgemodels.open_url import OpenUrl
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_COMMAND,
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_TOKEN,
    CONF_URL,
    Platform,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .config_flow import SystemBridgeConfigFlow
from .const import DOMAIN, MODULES
from .coordinator import SystemBridgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.UPDATE,
]

CONF_BRIDGE = "bridge"
CONF_KEY = "key"
CONF_TEXT = "text"

SERVICE_GET_PROCESS_BY_ID = "get_process_by_id"
SERVICE_GET_PROCESSES_BY_NAME = "get_processes_by_name"
SERVICE_OPEN_PATH = "open_path"
SERVICE_POWER_COMMAND = "power_command"
SERVICE_OPEN_URL = "open_url"
SERVICE_SEND_KEYPRESS = "send_keypress"
SERVICE_SEND_TEXT = "send_text"

POWER_COMMAND_MAP = {
    "hibernate": "power_hibernate",
    "lock": "power_lock",
    "logout": "power_logout",
    "restart": "power_restart",
    "shutdown": "power_shutdown",
    "sleep": "power_sleep",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
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
        async with asyncio.timeout(10):
            supported = await version.check_supported()
    except AuthenticationException as exception:
        _LOGGER.error("Authentication failed for %s: %s", entry.title, exception)
        raise ConfigEntryAuthFailed from exception
    except (ConnectionClosedException, ConnectionErrorException) as exception:
        raise ConfigEntryNotReady(
            f"Could not connect to {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception
    except TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
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
            "You are not running a supported version of System Bridge. Please update to the latest version."
        )

    coordinator = SystemBridgeDataUpdateCoordinator(
        hass,
        _LOGGER,
        entry=entry,
    )
    try:
        async with asyncio.timeout(10):
            await coordinator.async_get_data(MODULES)
    except AuthenticationException as exception:
        _LOGGER.error("Authentication failed for %s: %s", entry.title, exception)
        raise ConfigEntryAuthFailed from exception
    except (ConnectionClosedException, ConnectionErrorException) as exception:
        raise ConfigEntryNotReady(
            f"Could not connect to {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception
    except TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    try:
        # Wait for initial data
        async with asyncio.timeout(10):
            while not coordinator.is_ready:
                _LOGGER.debug(
                    "Waiting for initial data from %s (%s)",
                    entry.title,
                    entry.data[CONF_HOST],
                )
                await asyncio.sleep(1)
    except TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up all platforms except notify
    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    # Set up notify platform
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

    if hass.services.has_service(DOMAIN, SERVICE_OPEN_URL):
        return True

    def valid_device(device: str) -> str:
        """Check device is valid."""
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(device)
        if device_entry is not None:
            try:
                return next(
                    entry.entry_id
                    for entry in hass.config_entries.async_entries(DOMAIN)
                    if entry.entry_id in device_entry.config_entries
                )
            except StopIteration as exception:
                raise vol.Invalid(f"Could not find device {device}") from exception
        raise vol.Invalid(f"Device {device} does not exist")

    async def handle_get_process_by_id(service_call: ServiceCall) -> ServiceResponse:
        """Handle the get process by id service call."""
        _LOGGER.debug("Get process by id: %s", service_call.data)
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            service_call.data[CONF_BRIDGE]
        ]
        processes: list[Process] = coordinator.data.processes

        # Find process.id from list, raise ServiceValidationError if not found
        try:
            return asdict(
                next(
                    process
                    for process in processes
                    if process.id == service_call.data[CONF_ID]
                )
            )
        except StopIteration as exception:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="process_not_found",
                translation_placeholders={"id": service_call.data[CONF_ID]},
            ) from exception

    async def handle_get_processes_by_name(
        service_call: ServiceCall,
    ) -> ServiceResponse:
        """Handle the get process by name service call."""
        _LOGGER.debug("Get process by name: %s", service_call.data)
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            service_call.data[CONF_BRIDGE]
        ]
        processes: list[Process] = coordinator.data.processes
        # Find processes from list
        items: list[dict[str, Any]] = [
            asdict(process)
            for process in processes
            if process.name is not None
            and service_call.data[CONF_NAME].lower() in process.name.lower()
        ]

        return {
            "count": len(items),
            "processes": list(items),
        }

    async def handle_open_path(service_call: ServiceCall) -> ServiceResponse:
        """Handle the open path service call."""
        _LOGGER.debug("Open path: %s", service_call.data)
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            service_call.data[CONF_BRIDGE]
        ]
        response = await coordinator.websocket_client.open_path(
            OpenPath(path=service_call.data[CONF_PATH])
        )
        return asdict(response)

    async def handle_power_command(service_call: ServiceCall) -> ServiceResponse:
        """Handle the power command service call."""
        _LOGGER.debug("Power command: %s", service_call.data)
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            service_call.data[CONF_BRIDGE]
        ]
        response = await getattr(
            coordinator.websocket_client,
            POWER_COMMAND_MAP[service_call.data[CONF_COMMAND]],
        )()
        return asdict(response)

    async def handle_open_url(service_call: ServiceCall) -> ServiceResponse:
        """Handle the open url service call."""
        _LOGGER.debug("Open URL: %s", service_call.data)
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            service_call.data[CONF_BRIDGE]
        ]
        response = await coordinator.websocket_client.open_url(
            OpenUrl(url=service_call.data[CONF_URL])
        )
        return asdict(response)

    async def handle_send_keypress(service_call: ServiceCall) -> ServiceResponse:
        """Handle the send_keypress service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            service_call.data[CONF_BRIDGE]
        ]
        response = await coordinator.websocket_client.keyboard_keypress(
            KeyboardKey(key=service_call.data[CONF_KEY])
        )
        return asdict(response)

    async def handle_send_text(service_call: ServiceCall) -> ServiceResponse:
        """Handle the send_keypress service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            service_call.data[CONF_BRIDGE]
        ]
        response = await coordinator.websocket_client.keyboard_text(
            KeyboardText(text=service_call.data[CONF_TEXT])
        )
        return asdict(response)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PROCESS_BY_ID,
        handle_get_process_by_id,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_ID): cv.positive_int,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PROCESSES_BY_NAME,
        handle_get_processes_by_name,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_NAME): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_PATH,
        handle_open_path,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_PATH): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_POWER_COMMAND,
        handle_power_command,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_COMMAND): vol.In(POWER_COMMAND_MAP),
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_URL,
        handle_open_url,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_URL): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_KEYPRESS,
        handle_send_keypress,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_KEY): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TEXT,
        handle_send_text,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
                vol.Required(CONF_TEXT): cv.string,
            },
        ),
        supports_response=SupportsResponse.ONLY,
    )

    # Reload entry when its updated.
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
        hass.services.async_remove(DOMAIN, SERVICE_OPEN_PATH)
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
