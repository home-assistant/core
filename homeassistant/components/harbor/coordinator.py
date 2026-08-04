"""Coordinator for Harbor."""

import asyncio
import logging
from typing import Any, override
from uuid import uuid4

from harbor.config import HarborCameraConfig
from harbor.devices.camera import HarborCamera
from harbor.mqtt import DEFAULT_INITIAL_COMMANDS, HarborMQTTClient
from harbor.state import HarborDeviceState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import instance_id
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, MANUFACTURER, MODEL

LOGGER = logging.getLogger(__name__)

type HarborConfigEntry = ConfigEntry[HarborCoordinator]

# How long to wait for the first successful MQTT connection and the first
# device data to arrive before treating the camera as unreachable, both when
# validating the config flow and during setup.
CONNECT_TIMEOUT = 30.0


async def _discard_message(topic: str, payload: Any) -> None:
    """Ignore messages received while probing the connection."""


async def async_probe_camera(config: HarborCameraConfig) -> str | None:
    """Connect to a Harbor camera and return its friendly name, if any.

    Raises ``TimeoutError`` when no MQTT session can be established with the
    camera. Returns the camera's configured display name, or ``None`` when the
    camera is reachable but has no name (or does not answer the settings
    request in time).
    """
    connected = asyncio.Event()

    async def _on_connection_change(is_connected: bool) -> None:
        if is_connected:
            connected.set()

    client = HarborMQTTClient(
        config=config,
        # Subscribe to the responses topic so the get-settings reply can be
        # matched to its pending request; without a subscription the reply
        # never reaches the client and the request would time out.
        topics=[f"cameras/{config.serial}/responses/#"],
        message_handler=_discard_message,
        client_id=f"{DOMAIN}-{config.serial}-probe-{uuid4().hex[:8]}",
        on_connection_change=_on_connection_change,
        connection_grace_period=0,
    )
    await client.start()
    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            await connected.wait()
        try:
            settings = await client.get_settings()
        except TimeoutError, ConnectionError:
            return None
        if settings.settings is None:
            return None
        return settings.settings.preference_display_name
    finally:
        await client.stop()


class HarborCoordinator(DataUpdateCoordinator[HarborDeviceState]):
    """Own the MQTT transport and state for a single Harbor camera."""

    config_entry: HarborConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HarborConfigEntry,
        config: HarborCameraConfig,
    ) -> None:
        """Initialize the Harbor coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{config.serial}",
        )
        self._config = config
        self.device = HarborCamera(config)
        self.data = self.device.state
        self.connected = False
        self._ssl_context_cache: dict[str, Any] = {}
        self._mqtt_client: HarborMQTTClient | None = None
        self._connected_event = asyncio.Event()
        self._data_event = asyncio.Event()
        self._unsubscribe_updates = self.device.subscribe_updates(
            self._handle_device_update
        )

    async def async_start(self) -> None:
        """Start the Harbor MQTT client."""
        hass_instance_id = await instance_id.async_get(self.hass)
        client_id = (
            f"{DOMAIN}-{hass_instance_id[:8]}-"
            f"{self.config_entry.entry_id[:8]}-{self._config.serial}"
        )
        self._mqtt_client = HarborMQTTClient(
            config=self._config,
            topics=self.device.get_topics(),
            message_handler=self.device.handle_message,
            client_id=client_id,
            ssl_context_cache=self._ssl_context_cache,
            on_connection_change=self._async_set_connected,
            # Fetch the full settings snapshot on every (re)connection so the
            # device name and settings-derived state populate immediately
            # instead of waiting for the next heartbeat.
            initial_commands=DEFAULT_INITIAL_COMMANDS,
        )
        await self._mqtt_client.start()

    async def async_wait_until_ready(self) -> None:
        """Wait for the first MQTT connection and the first device data.

        Registering entities only once the camera's first message has
        arrived means the device registry sees the real name and firmware
        from the start, instead of a placeholder that would otherwise
        persist until the next reload.

        Raises ``TimeoutError`` if the camera does not connect and report
        data in time.
        """
        async with asyncio.timeout(CONNECT_TIMEOUT):
            await self._connected_event.wait()
            await self._data_event.wait()

    @override
    async def async_shutdown(self) -> None:
        """Stop the MQTT client and release device resources."""
        await super().async_shutdown()
        if self._mqtt_client is not None:
            await self._mqtt_client.stop()
            self._mqtt_client = None
        self._unsubscribe_updates()
        self.device.shutdown()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the Harbor camera."""
        state = self.data
        return DeviceInfo(
            identifiers={(DOMAIN, state.serial)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=state.display_name or f"{MODEL} {state.serial}",
            serial_number=state.serial,
            sw_version=state.os_version,
        )

    def _handle_device_update(self, state: HarborDeviceState) -> None:
        """Mirror a library device update into Home Assistant."""
        self._data_event.set()
        self.async_set_updated_data(state)

    async def _async_set_connected(self, connected: bool) -> None:
        """Propagate the MQTT connection state to entity availability."""
        if connected:
            self._connected_event.set()
        if self.connected == connected:
            return
        self.connected = connected
        self.async_update_listeners()
