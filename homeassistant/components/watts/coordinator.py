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
        self._devices: dict[str, Device] = {}
        self._is_initialized = False

    async def async_config_entry_first_refresh(self) -> None:
        """Perform initial discovery of devices."""
        try:
            await self._discover_devices()
            self.async_set_updated_data(self._devices)
        except (ConnectionError, TimeoutError, ValueError) as err:
            _LOGGER.error("Initial device discovery failed: %s", err)
            raise UpdateFailed(f"Initial discovery failed: {err}") from err

    async def _discover_devices(self) -> None:
        """Discover devices from API."""
        devices_list = await self.client.discover_devices()
        self._devices = {device.device_id: device for device in devices_list}
        self._is_initialized = True
        _LOGGER.info("Initial discovery completed with %d devices", len(self._devices))

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data from Watts Vision API for all devices."""
        try:
            if not self._is_initialized:
                # First loading, discover devices
                await self._discover_devices()
            else:
                device_ids = list(self._devices.keys())

                if not device_ids:
                    _LOGGER.warning("No devices to update")
                else:
                    updated_devices = await self.client.get_devices_report(device_ids)

                    for device_id, device in updated_devices.items():
                        self._devices[device_id] = device

                    _LOGGER.debug("Updated %d devices", len(updated_devices))

        except (ConnectionError, TimeoutError, ValueError) as err:
            _LOGGER.error("API error during devices update: %s", err)
            raise UpdateFailed(f"API error during devices update: {err}") from err
        else:
            return self._devices

    @property
    def device_ids(self) -> list[str]:
        """Get list of all device IDs."""
        return list(self._devices.keys())


class WattsVisionDeviceCoordinator(DataUpdateCoordinator[Device | None]):
    """Device coordinator for individual updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WattsVisionClient,
        config_entry: ConfigEntry,
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
        self._fast_polling_until: datetime | None = None

    async def _async_update_data(self) -> Device | None:
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
        else:
            if device:
                _LOGGER.debug("Refreshed device %s", self.device_id)
                return device
            _LOGGER.warning("Device %s not found during refresh", self.device_id)
            return None

    def trigger_fast_polling(self, duration: int = 60) -> None:
        """Activate fast polling for a specified duration after a command."""
        self._fast_polling_until = datetime.now() + timedelta(seconds=duration)
        self.update_interval = timedelta(seconds=FAST_POLLING_INTERVAL)
        _LOGGER.debug(
            "Device %s: Activated fast polling for %d seconds", self.device_id, duration
        )
