"""The System Bridge integration."""
from __future__ import annotations

import asyncio
import logging

import async_timeout
from systembridgeconnector.exceptions import (
    BadMessageException,
    ConnectionErrorException,
)
from systembridgeconnector.websocket_client import WebSocketClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_URL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MODULES, SystemBridgeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

# CONF_ARGUMENTS = "arguments"
CONF_BRIDGE = "bridge"
# CONF_KEY = "key"
# CONF_MODIFIERS = "modifiers"
# CONF_TEXT = "text"
# CONF_WAIT = "wait"

SERVICE_OPEN_PATH = "open_path"
SERVICE_OPEN_URL = "open_url"
# SERVICE_SEND_KEYPRESS = "send_keypress"
# SERVICE_SEND_TEXT = "send_text"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up System Bridge from a config entry."""

    websocket_client = WebSocketClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_API_KEY],
    )
    try:
        await websocket_client.connect()
        await websocket_client.close()
    except ConnectionErrorException as exception:
        raise ConfigEntryNotReady(
            f"Could not connect to {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

    coordinator = SystemBridgeDataUpdateCoordinator(hass, _LOGGER, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    _LOGGER.debug("Data: %s", coordinator.data)

    # Wait for initial data
    try:
        async with async_timeout.timeout(60):
            while (
                coordinator.data is None
                or coordinator.data == {}
                or all(module not in coordinator.data for module in MODULES)
                # or coordinator.data["battery"] is None
                # or coordinator.data["system"] is None
            ):
                _LOGGER.debug(
                    "Waiting for initial data from %s (%s): %s",
                    entry.title,
                    entry.data[CONF_HOST],
                    coordinator.data,
                )
                await asyncio.sleep(1)
    except asyncio.TimeoutError as exception:
        raise ConfigEntryNotReady(
            f"Timed out waiting for {entry.title} ({entry.data[CONF_HOST]})."
        ) from exception

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    if hass.services.has_service(DOMAIN, SERVICE_OPEN_URL):
        return True

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

        try:
            await coordinator.websocket_client.open_path(call.data[CONF_PATH])
        except BadMessageException as exception:
            raise HomeAssistantError("Error sending") from exception

    async def handle_open_url(call: ServiceCall) -> None:
        """Handle the open url service call."""
        _LOGGER.info("Open: %s", call.data)
        coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
            call.data[CONF_BRIDGE]
        ]

        try:
            await coordinator.websocket_client.open_url(call.data[CONF_URL])
        except BadMessageException as exception:
            raise HomeAssistantError("Error sending") from exception

    # async def handle_send_keypress(call: ServiceCall) -> None:
    #     """Handle the send_keypress service call."""
    #     coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
    #         call.data[CONF_BRIDGE]
    #     ]
    #     bridge: Bridge = coordinator.data

    #     keyboard_payload: KeyboardPayload = {
    #         CONF_KEY: call.data[CONF_KEY],
    #         CONF_MODIFIERS: shlex.split(call.data.get(CONF_MODIFIERS, "")),
    #     }

    #     _LOGGER.debug("Keypress payload: %s", keyboard_payload)
    #     try:
    #         await bridge.async_send_keypress(keyboard_payload)
    #     except (BridgeAuthenticationException, *BRIDGE_CONNECTION_ERRORS) as exception:
    #         raise HomeAssistantError("Error sending") from exception
    #     _LOGGER.debug("Sent keypress request")

    # async def handle_send_text(call: ServiceCall) -> None:
    #     """Handle the send_keypress service call."""
    #     coordinator: SystemBridgeDataUpdateCoordinator = hass.data[DOMAIN][
    #         call.data[CONF_BRIDGE]
    #     ]
    #     bridge: Bridge = coordinator.data

    #     keyboard_payload: KeyboardPayload = {CONF_TEXT: call.data[CONF_TEXT]}

    #     _LOGGER.debug("Text payload: %s", keyboard_payload)
    #     try:
    #         await bridge.async_send_keypress(keyboard_payload)
    #     except (BridgeAuthenticationException, *BRIDGE_CONNECTION_ERRORS) as exception:
    #         raise HomeAssistantError("Error sending") from exception
    #     _LOGGER.debug("Sent text request")

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

    # hass.services.async_register(
    #     DOMAIN,
    #     SERVICE_SEND_KEYPRESS,
    #     handle_send_keypress,
    #     schema=vol.Schema(
    #         {
    #             vol.Required(CONF_BRIDGE): valid_device,
    #             vol.Required(CONF_KEY): cv.string,
    #             vol.Optional(CONF_MODIFIERS): cv.string,
    #         },
    #     ),
    # )

    # hass.services.async_register(
    #     DOMAIN,
    #     SERVICE_SEND_TEXT,
    #     handle_send_text,
    #     schema=vol.Schema(
    #         {
    #             vol.Required(CONF_BRIDGE): valid_device,
    #             vol.Required(CONF_TEXT): cv.string,
    #         },
    #     ),
    # )

    # Reload entry when its updated.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
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
        # hass.services.async_remove(DOMAIN, SERVICE_SEND_KEYPRESS)
        # hass.services.async_remove(DOMAIN, SERVICE_SEND_TEXT)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)


class SystemBridgeEntity(CoordinatorEntity[SystemBridgeDataUpdateCoordinator]):
    """Defines a base System Bridge entity."""

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        api_port: int,
        key: str,
        name: str | None,
    ) -> None:
        """Initialize the System Bridge entity."""
        super().__init__(coordinator)

        self._hostname = coordinator.data["system"]["hostname"]
        self._key = f"{self._hostname}_{key}"
        self._name = f"{self._hostname} {name}"
        self._configuration_url = f"http://{self._hostname}:{api_port}/app/settings"
        self._mac_address = coordinator.data["system"]["mac_address"]
        self._version = coordinator.data["system"]["version"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._key

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name


class SystemBridgeDeviceEntity(SystemBridgeEntity):
    """Defines a System Bridge device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this System Bridge instance."""
        return DeviceInfo(
            configuration_url=self._configuration_url,
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_address)},
            name=self._hostname,
            sw_version=self._version,
        )
