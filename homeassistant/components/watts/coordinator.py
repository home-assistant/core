"""Data coordinator for Watts Vision integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from visionpluspython.client import WattsVisionClient
from visionpluspython.exceptions import (
    WattsVisionAuthError,
    WattsVisionConnectionError,
    WattsVisionDeviceError,
    WattsVisionError,
    WattsVisionTimeoutError,
)
from visionpluspython.models import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, FAST_POLLING_INTERVAL, UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import WattsVisionRuntimeData

    type WattsVisionConfigEntry = ConfigEntry[WattsVisionRuntimeData]

_LOGGER = logging.getLogger(__name__)


class WattsVisionHubCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Hub coordinator for bulk device discovery and updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WattsVisionClient,
        config_entry: WattsVisionConfigEntry,
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

    async def async_setup(self) -> None:
        """Set up the coordinator by discovering devices."""
        try:
            devices_list = await self.client.discover_devices()
        except WattsVisionAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (
            WattsVisionConnectionError,
            WattsVisionTimeoutError,
            WattsVisionDeviceError,
            WattsVisionError,
            ConnectionError,
            TimeoutError,
            ValueError,
        ) as err:
            raise ConfigEntryNotReady("Failed to discover devices") from err

        devices = {device.device_id: device for device in devices_list}
        _LOGGER.info("Initial discovery completed with %d devices", len(devices))
        self.async_set_updated_data(devices)

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data from Watts Vision API for all devices."""
        device_ids = list(self.data.keys())
        if not device_ids:
            return {}

        try:
            devices = await self.client.get_devices_report(device_ids)
        except WattsVisionAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (
            WattsVisionConnectionError,
            WattsVisionTimeoutError,
            WattsVisionDeviceError,
            WattsVisionError,
            ConnectionError,
            TimeoutError,
            ValueError,
        ) as err:
            raise UpdateFailed("Failed to update devices") from err

        _LOGGER.debug("Updated %d devices", len(devices))
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
        config_entry: WattsVisionConfigEntry,
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
        self.unsubscribe_hub_listener = hub_coordinator.async_add_listener(
            self._handle_hub_update
        )

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
        except WattsVisionAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (
            WattsVisionConnectionError,
            WattsVisionTimeoutError,
            WattsVisionDeviceError,
            WattsVisionError,
            ConnectionError,
            TimeoutError,
            ValueError,
        ) as err:
            raise UpdateFailed(f"Failed to refresh device {self.device_id}") from err

        if not device:
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
