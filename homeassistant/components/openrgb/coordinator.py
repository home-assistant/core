"""DataUpdateCoordinator for OpenRGB."""

import asyncio
import logging
from typing import override

from openrgb import OpenRGBClient
from openrgb.orgb import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONNECTION_ERRORS,
    DEFAULT_CLIENT_NAME,
    DOMAIN,
    SCAN_INTERVAL,
    UID_SEPARATOR,
    UNSTABLE_LOCATIONS,
)

_LOGGER = logging.getLogger(__name__)

type OpenRGBConfigEntry = ConfigEntry[OpenRGBCoordinator]


def stable_location(location: str) -> str:
    """Return the location with any unstable connection path replaced."""
    for prefix, replacement in UNSTABLE_LOCATIONS.items():
        if location.startswith(prefix):
            return replacement
    return location


class OpenRGBCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching OpenRGB data."""

    client: OpenRGBClient

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenRGBConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=0.5, immediate=False
            ),
        )
        self.host = config_entry.data[CONF_HOST]
        self.port = config_entry.data[CONF_PORT]
        self.entry_id = config_entry.entry_id
        self.server_address = f"{self.host}:{self.port}"
        self.client_lock = asyncio.Lock()

        config_entry.async_on_unload(self.async_client_disconnect)

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator by connecting to the OpenRGB SDK server."""
        try:
            self.client = await self.hass.async_add_executor_job(
                OpenRGBClient,
                self.host,
                self.port,
                DEFAULT_CLIENT_NAME,
            )
        except CONNECTION_ERRORS as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={
                    "server_address": self.server_address,
                    "error": str(err),
                },
            ) from err

    @override
    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data from OpenRGB."""
        async with self.client_lock:
            try:
                await self.hass.async_add_executor_job(self._client_update)
            except CONNECTION_ERRORS as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="communication_error",
                    translation_placeholders={
                        "server_address": self.server_address,
                        "error": str(err),
                    },
                ) from err

        # Return devices indexed by their key
        return {self._get_device_key(device): device for device in self.client.devices}

    def _client_update(self) -> None:
        try:
            self.client.update()
        except CONNECTION_ERRORS:
            # Try to reconnect once
            self.client.disconnect()
            self.client.connect()
            self.client.update()

    def _get_device_key(self, device: Device) -> str:
        """Build a stable device key.

        Note: the OpenRGB device.id is intentionally not used because it is just
        a positional index that can change when devices are added or removed.

        For HID and USB devices the location holds the current connection path,
        for example "HID: /dev/hidraw14". Those paths are reassigned when a
        device reconnects and on every reboot, so a device that reports a serial
        is identified by that serial and its location is replaced with a
        constant. Locations on other buses are kept as they are.
        """
        # Devices that cannot report a serial may return padding instead, and
        # "none" is the value written for a serial the device did not report, so
        # it cannot also act as one
        serial = (device.metadata.serial or "").strip()
        if serial == "none":
            serial = ""
        location = device.metadata.location or "none"

        if serial:
            location = stable_location(location)

        parts = (
            self.entry_id,
            device.type.name,
            device.metadata.vendor or "none",
            device.metadata.description or "none",
            serial or "none",
            location,
        )
        # Double pipe is readable and is unlikely to appear in metadata
        return UID_SEPARATOR.join(parts)

    async def async_client_disconnect(self, *args) -> None:
        """Disconnect the OpenRGB client."""
        if not hasattr(self, "client"):
            # If async_config_entry_first_refresh failed, client will not exist
            return

        async with self.client_lock:
            await self.hass.async_add_executor_job(self.client.disconnect)

    def get_client_protocol_version(self) -> str:
        """Get the OpenRGB client protocol version."""
        return f"{self.client.protocol_version} (Protocol)"

    def get_device_name(self, device_key: str) -> str:
        """Get device name with suffix if there are duplicates."""
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
        return device_name  # pragma: no cover
