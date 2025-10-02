"""DataUpdateCoordinator for OpenRGB."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from openrgb import OpenRGBClient
from openrgb.orgb import Device
from openrgb.utils import OpenRGBDisconnected, RGBColor, SDKVersionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_CLIENT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

type OpenRGBConfigEntry = ConfigEntry[OpenRGBCoordinator]


class OpenRGBCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching OpenRGB data."""

    _client: OpenRGBClient | None = None
    _client_lock: asyncio.Lock

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
            config_entry=config_entry,
        )
        self.host = config_entry.data[CONF_HOST]
        self.port = config_entry.data[CONF_PORT]
        self.entry_id = config_entry.entry_id
        self.server_address = f"{self.host}:{self.port}"
        self._client_lock = asyncio.Lock()

        # Register listener for Home Assistant stop event
        self._stop_listener = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_client_disconnect
        )

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data from OpenRGB."""
        try:
            if self._client is None:
                await self._async_client_connect()
            else:
                try:
                    # Try to update existing client data
                    await self._async_client_update()
                except OpenRGBDisconnected:
                    # If the client was disconnected, try to reconnect once
                    await self._async_client_connect()
                    # And then try to update once again
                    await self._async_client_update()
        except (
            ConnectionRefusedError,
            OpenRGBDisconnected,
            OSError,
            SDKVersionError,
        ) as err:
            await self.async_client_disconnect()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_connect",
                translation_placeholders={"server_address": self.server_address},
            ) from err

        if self._client is None:
            return {}

        # Return devices indexed by their key
        return {self._get_device_key(device): device for device in self._client.devices}

    def _get_device_key(self, device: Device) -> str:
        """Build a stable device key.

        Note: the OpenRGB device.id is intentionally not used because it is just
        a positional index that can change when devices are added or removed.
        """
        parts = (
            self.entry_id,
            device.type.name,
            device.metadata.vendor or "none",
            device.metadata.description or "none",
            device.metadata.serial or "none",
            device.metadata.location or "none",
        )
        # Double pipe is readable and is unlikely to appear in metadata
        return "||".join(parts)

    async def _async_client_connect(self) -> None:
        """Connect to the OpenRGB client."""
        async with self._client_lock:
            await self._async_client_disconnect_unlocked()
            self._client = await self.hass.async_add_executor_job(
                OpenRGBClient, self.host, self.port, DEFAULT_CLIENT_NAME
            )

    async def async_client_disconnect(self, *args) -> None:
        """Disconnect the OpenRGB client."""
        async with self._client_lock:
            await self._async_client_disconnect_unlocked()

    async def _async_client_disconnect_unlocked(self) -> None:
        """Disconnect the OpenRGB client without acquiring the lock."""
        if self._client is None:
            return
        await self.hass.async_add_executor_job(self._client.disconnect)
        self._client = None

    def get_client_protocol_version(self) -> str | None:
        """Get the OpenRGB client protocol version."""
        if self._client is None:
            return None
        return f"{self._client.protocol_version} (Protocol)"

    async def _async_client_update(self) -> None:
        """Update the OpenRGB client data."""
        if self._client is None:
            # Should never happen, but just in case
            return
        async with self._client_lock:
            await self.hass.async_add_executor_job(self._client.update)

    async def async_device_set_color(self, device: Device, color: RGBColor) -> None:
        """Set the color of a device."""
        async with self._client_lock:
            await self.hass.async_add_executor_job(device.set_color, color, True)

    async def async_device_set_mode(self, device: Device, mode: str) -> None:
        """Set the mode of a device."""
        async with self._client_lock:
            await self.hass.async_add_executor_job(device.set_mode, mode)

    def get_device_name(self, device_key: str) -> str:
        """Get device name with suffix if there are duplicates."""
        if device_key not in self.data:
            return ""

        device = self.data[device_key]
        device_name = device.name

        devices_with_same_name = [
            (key, dev) for key, dev in self.data.items() if dev.name == device_name
        ]

        if len(devices_with_same_name) == 1:
            return device_name

        # Sort duplicates by device.id
        devices_with_same_name.sort(key=lambda x: x[1].id)

        # Return name with numeric suffix based on the sorted order
        for idx, (key, _) in enumerate(devices_with_same_name, start=1):
            if key == device_key:
                return f"{device_name} {idx}"

        # Should never reach here, but just in case
        return device_name
