"""Data coordinator for Watts Vision integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from visionpluspython.client import WattsVisionClient
from visionpluspython.models import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, FAST_POLLING_INTERVAL, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class WattsVisionHubCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Hub coordinator for bulk device discovery and updates."""

    def __init__(
        self, hass: HomeAssistant, client: WattsVisionClient, config_entry: ConfigEntry
    ) -> None:
        """Initialize the hub coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data from Watts Vision API for all devices."""
        try:
            if not self.data:
                # First loading, discover devices
                devices_list = await self.client.discover_devices()
                devices = {device.device_id: device for device in devices_list}
                _LOGGER.info(
                    "Initial discovery completed with %d devices", len(devices)
                )
            else:
                device_ids = list(self.data.keys())

                if not device_ids:
                    _LOGGER.warning("No devices to update")
                    devices = self.data
                else:
                    devices = await self.client.get_devices_report(device_ids)
                    _LOGGER.debug("Updated %d devices", len(devices))

        except (ConnectionError, TimeoutError, ValueError) as err:
            _LOGGER.error("API error during devices update: %s", err)
            raise UpdateFailed(f"API error during devices update: {err}") from err
        else:
            return devices

    @property
    def device_ids(self) -> list[str]:
        """Get list of all device IDs."""
        return list((self.data or {}).keys())


class WattsVisionDeviceCoordinator(DataUpdateCoordinator[Device]):
    """Device coordinator for individual updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WattsVisionClient,
        config_entry: ConfigEntry,
        hub_coordinator: WattsVisionHubCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the device coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_id}",
            update_interval=None,  # Manual refresh only
            config_entry=config_entry,
        )
        self.client = client
        self.device_id = device_id
        self.hub_coordinator = hub_coordinator
        self._fast_polling_until: datetime | None = None

        # Listen to hub coordinator updates
        hub_coordinator.async_add_listener(self._handle_hub_update)

    def _handle_hub_update(self) -> None:
        """Handle updates from hub coordinator."""
        if self.hub_coordinator.data and self.device_id in self.hub_coordinator.data:
            device = self.hub_coordinator.data[self.device_id]
            self.async_set_updated_data(device)

    async def _async_update_data(self) -> Device:
        """Refresh specific device."""
        if self._fast_polling_until and datetime.now() > self._fast_polling_until:
            self._fast_polling_until = None
            self.update_interval = None
            _LOGGER.debug(
                "Device %s: Fast polling period ended, returning to manual refresh",
                self.device_id,
            )

        try:
            device = await self.client.get_device(self.device_id, refresh=True)
        except (ConnectionError, TimeoutError, ValueError) as err:
            _LOGGER.error("Failed to refresh device %s: %s", self.device_id, err)
            raise UpdateFailed(
                f"Failed to refresh device {self.device_id}: {err}"
            ) from err

        if not device:
            _LOGGER.error("Device %s not found during refresh", self.device_id)
            raise UpdateFailed(f"Device {self.device_id} not found")

        _LOGGER.debug("Refreshed device %s", self.device_id)
        return device

    def trigger_fast_polling(self, duration: int = 60) -> None:
        """Activate fast polling for a specified duration after a command."""
        self._fast_polling_until = datetime.now() + timedelta(seconds=duration)
        self.update_interval = timedelta(seconds=FAST_POLLING_INTERVAL)
        _LOGGER.debug(
            "Device %s: Activated fast polling for %d seconds", self.device_id, duration
        )
