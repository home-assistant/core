"""Data coordinator for Watts Vision integration."""

from __future__ import annotations

from dataclasses import dataclass
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
from visionpluspython.models import Device, ThermostatDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DISCOVERY_INTERVAL_MINUTES,
    DOMAIN,
    FAST_POLLING_INTERVAL_SECONDS,
    UPDATE_INTERVAL_SECONDS,
)

if TYPE_CHECKING:
    from . import WattsVisionRuntimeData

    type WattsVisionConfigEntry = ConfigEntry[WattsVisionRuntimeData]

_LOGGER = logging.getLogger(__name__)


@dataclass
class WattsVisionThermostatData:
    """Data class for thermostat device coordinator."""

    thermostat: ThermostatDevice


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
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            config_entry=config_entry,
        )
        self.client = client
        self._last_discovery: datetime | None = None
        self.previous_devices: set[str] = set()

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data and periodic device discovery."""
        now = datetime.now()
        is_first_refresh = self._last_discovery is None
        discovery_interval_elapsed = (
            self._last_discovery is not None
            and now - self._last_discovery
            >= timedelta(minutes=DISCOVERY_INTERVAL_MINUTES)
        )

        if is_first_refresh or discovery_interval_elapsed:
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
                if is_first_refresh:
                    raise ConfigEntryNotReady("Failed to discover devices") from err
                _LOGGER.warning(
                    "Periodic discovery failed: %s, falling back to update", err
                )
            else:
                self._last_discovery = now
                devices = {device.device_id: device for device in devices_list}

                current_devices = set(devices.keys())
                if stale_devices := self.previous_devices - current_devices:
                    await self._remove_stale_devices(stale_devices)

                self.previous_devices = current_devices
                return devices

        # Regular update of existing devices
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

    async def _remove_stale_devices(self, stale_device_ids: set[str]) -> None:
        """Remove stale devices."""
        assert self.config_entry is not None
        device_registry = dr.async_get(self.hass)

        for device_id in stale_device_ids:
            _LOGGER.info("Removing stale device: %s", device_id)

            device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
            if device:
                device_registry.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

    @property
    def device_ids(self) -> list[str]:
        """Get list of all device IDs."""
        return list((self.data or {}).keys())


class WattsVisionThermostatCoordinator(
    DataUpdateCoordinator[WattsVisionThermostatData]
):
    """Thermostat device coordinator for individual updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WattsVisionClient,
        config_entry: WattsVisionConfigEntry,
        hub_coordinator: WattsVisionHubCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the thermostat coordinator."""
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
            assert isinstance(device, ThermostatDevice)
            self.async_set_updated_data(WattsVisionThermostatData(thermostat=device))

    async def _async_update_data(self) -> WattsVisionThermostatData:
        """Refresh specific thermostat device."""
        if self._fast_polling_until and datetime.now() > self._fast_polling_until:
            self._fast_polling_until = None
            self.update_interval = None
            _LOGGER.debug(
                "Device %s: Fast polling period ended, returning to manual refresh",
                self.device_id,
            )

        try:
            device = await self.client.get_device(self.device_id, refresh=True)
        except (
            WattsVisionAuthError,
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

        assert isinstance(device, ThermostatDevice)
        _LOGGER.debug("Refreshed thermostat %s", self.device_id)
        return WattsVisionThermostatData(thermostat=device)

    def trigger_fast_polling(self, duration: int = 60) -> None:
        """Activate fast polling for a specified duration after a command."""
        self._fast_polling_until = datetime.now() + timedelta(seconds=duration)
        self.update_interval = timedelta(seconds=FAST_POLLING_INTERVAL_SECONDS)
        _LOGGER.debug(
            "Device %s: Activated fast polling for %d seconds", self.device_id, duration
        )
