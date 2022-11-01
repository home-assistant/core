"""Services for the SystemBridge integration."""

import logging

from systembridgeconnector.models.keyboard_key import KeyboardKey
from systembridgeconnector.models.keyboard_text import KeyboardText
from systembridgeconnector.models.open_path import OpenPath
from systembridgeconnector.models.open_url import OpenUrl
import voluptuous as vol

from homeassistant.const import CONF_PATH, CONF_URL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import SystemBridgeDataUpdateCoordinator

CONF_BRIDGE = "bridge"
CONF_KEY = "key"
CONF_TEXT = "text"

SERVICE_OPEN_PATH = "open_path"
SERVICE_OPEN_URL = "open_url"
SERVICE_SEND_KEYPRESS = "send_keypress"
SERVICE_SEND_TEXT = "send_text"
SERVICE_SLEEP = "sleep"
SERVICE_HIBERNATE = "hibernate"
SERVICE_RESTART = "restart"
SERVICE_SHUTDOWN = "shutdown"
SERVICE_LOCK = "lock"
SERVICE_LOGOUT = "logout"

_LOGGER = logging.getLogger(__name__)


def register(hass: HomeAssistant) -> None:
    """Register SystemBridge services."""

    if hass.services.has_service(DOMAIN, SERVICE_OPEN_URL):
        return

    def valid_device(device: str):
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

    async def handle_sleep(call: ServiceCall) -> None:
        """Handle the sleep service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.power_sleep()

    async def handle_hibernate(call: ServiceCall) -> None:
        """Handle the hibernate service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.power_hibernate()

    async def handle_restart(call: ServiceCall) -> None:
        """Handle the restart service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.power_restart()

    async def handle_shutdown(call: ServiceCall) -> None:
        """Handle the shutdown service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.power_shutdown()

    async def handle_lock(call: ServiceCall) -> None:
        """Handle the lock service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.power_lock()

    async def handle_logout(call: ServiceCall) -> None:
        """Handle the logout service call."""
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]
        await coordinator.websocket_client.power_logout()

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

    hass.services.async_register(
        DOMAIN,
        SERVICE_SLEEP,
        handle_sleep,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
            },
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_HIBERNATE,
        handle_hibernate,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
            },
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTART,
        handle_restart,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
            },
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SHUTDOWN,
        handle_shutdown,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
            },
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOCK,
        handle_lock,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
            },
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOGOUT,
        handle_logout,
        schema=vol.Schema(
            {
                vol.Required(CONF_BRIDGE): valid_device,
            },
        ),
    )


def remove(hass: HomeAssistant) -> None:
    """Unregister SystemBridge services."""
    hass.services.async_remove(DOMAIN, SERVICE_OPEN_PATH)
    hass.services.async_remove(DOMAIN, SERVICE_OPEN_URL)
    hass.services.async_remove(DOMAIN, SERVICE_SEND_KEYPRESS)
    hass.services.async_remove(DOMAIN, SERVICE_SEND_TEXT)
    hass.services.async_remove(DOMAIN, SERVICE_SLEEP)
    hass.services.async_remove(DOMAIN, SERVICE_HIBERNATE)
    hass.services.async_remove(DOMAIN, SERVICE_RESTART)
    hass.services.async_remove(DOMAIN, SERVICE_SHUTDOWN)
    hass.services.async_remove(DOMAIN, SERVICE_LOCK)
    hass.services.async_remove(DOMAIN, SERVICE_LOGOUT)
