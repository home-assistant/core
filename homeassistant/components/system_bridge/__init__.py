"""The System Bridge integration."""
from __future__ import annotations

import asyncio
import logging

from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.models.keyboard_key import KeyboardKey
from systembridgeconnector.models.keyboard_text import KeyboardText
from systembridgeconnector.models.open_path import OpenPath
from systembridgeconnector.models.open_url import OpenUrl
from systembridgeconnector.version import SUPPORTED_VERSION, Version
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_COMMAND,
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_URL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
        entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )
    try:
        async with asyncio.timeout(10):
            if not await version.check_supported():
                raise ConfigEntryNotReady(
                    "You are not running a supported version of System Bridge. Please"
                    f" update to {SUPPORTED_VERSION} or higher."
                )
    except AuthenticationException as exception:
        _LOGGER.error("Authentication failed for %s: %s", entry.title, exception)
        raise ConfigEntryAuthFailed from exception
    except (ConnectionClosedException, ConnectionErrorException) as exception:
        raise ConfigEntryNotReady(
            f"Could not connect to {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception
    except asyncio.TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

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
    except asyncio.TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

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
    except asyncio.TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

    _LOGGER.debug(
        "Initial coordinator data for %s (%s):\n%s",
        entry.title,
        entry.data[CONF_HOST],
        coordinator.data.json(),
    )

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
                raise vol.Invalid from exception
        raise vol.Invalid(f"Device {device} does not exist")

    async def handle_open_path(call: ServiceCall) -> None:
        """Handle the open path service call."""
        _LOGGER.info("Open: %s", call.data)
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.open_path(
            OpenPath(path=call.data[CONF_PATH])
        )

    async def handle_power_command(call: ServiceCall) -> None:
        """Handle the power command service call."""
        _LOGGER.info("Power command: %s", call.data)
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await getattr(
            coordinator.websocket_client,
            POWER_COMMAND_MAP[call.data[CONF_COMMAND]],
        )()

    async def handle_open_url(call: ServiceCall) -> None:
        """Handle the open url service call."""
        _LOGGER.info("Open: %s", call.data)
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.open_url(OpenUrl(url=call.data[CONF_URL]))

    async def handle_send_keypress(call: ServiceCall) -> None:
        """Handle the send_keypress service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.keyboard_keypress(
            KeyboardKey(key=call.data[CONF_KEY])
        )

    async def handle_send_text(call: ServiceCall) -> None:
        """Handle the send_keypress service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.keyboard_text(
            KeyboardText(text=call.data[CONF_TEXT])
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
