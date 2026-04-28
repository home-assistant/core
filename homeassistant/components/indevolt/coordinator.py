"""Home Assistant integration for Indevolt device."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final

from aiohttp import ClientError
from indevolt_api import (
    IndevoltAPI,
    IndevoltConfig,
    IndevoltEnergyMode,
    IndevoltRealtimeAction,
    TimeOutException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_GENERATION,
    CONF_SERIAL_NUMBER,
    DEFAULT_PORT,
    DOMAIN,
    SENSOR_KEYS,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL: Final = 30

type IndevoltConfigEntry = ConfigEntry[IndevoltCoordinator]


class DeviceTimeoutError(HomeAssistantError):
    """Raised when device push times out."""


class DeviceConnectionError(HomeAssistantError):
    """Raised when device push fails due to connection issues."""


class IndevoltCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fetching and pushing data to indevolt devices."""

    friendly_name: str
    config_entry: IndevoltConfigEntry
    firmware_version: str | None
    serial_number: str
    device_model: str
    generation: int

    def __init__(self, hass: HomeAssistant, entry: IndevoltConfigEntry) -> None:
        """Initialize the indevolt coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            config_entry=entry,
        )

        # Initialize Indevolt API
        self.api = IndevoltAPI(
            host=entry.data[CONF_HOST],
            port=DEFAULT_PORT,
            session=async_get_clientsession(hass),
        )

        self.friendly_name: str = entry.title
        self.serial_number: str = entry.data[CONF_SERIAL_NUMBER]
        self.device_model: str = entry.data[CONF_MODEL]
        self.generation: int = entry.data[CONF_GENERATION]

    async def _async_setup(self) -> None:
        """Fetch device info once on boot."""
        try:
            config_data = await self.api.get_config()
        except TimeOutException as err:
            raise ConfigEntryNotReady(
                f"Device config retrieval timed out: {err}"
            ) from err

        # Cache device information
        device_data = config_data.get("device", {})

        self.firmware_version = device_data.get("fw")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch raw JSON data from the device."""
        sensor_keys = SENSOR_KEYS[self.generation]

        try:
            return await self.api.fetch_data(sensor_keys)
        except TimeOutException as err:
            raise UpdateFailed(f"Device update timed out: {err}") from err

    async def async_push_data(self, sensor_key: str, value: Any) -> bool:
        """Push/write data values to given key on the device."""
        try:
            return await self.api.set_data(sensor_key, value)
        except TimeOutException as err:
            raise DeviceTimeoutError(f"Device push timed out: {err}") from err
        except (ClientError, ConnectionError, OSError) as err:
            raise DeviceConnectionError(f"Device push failed: {err}") from err

    async def async_switch_energy_mode(
        self, target_mode: IndevoltEnergyMode, refresh: bool = True
    ) -> None:
        """Attempt to switch device to given energy mode."""
        current_mode = self.data.get(IndevoltConfig.READ_ENERGY_MODE)

        # Ensure current energy mode is known
        if current_mode is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_retrieve_current_energy_mode",
            )

        # Ensure device is not in "Outdoor/Portable mode"
        if current_mode == IndevoltEnergyMode.OUTDOOR_PORTABLE:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="energy_mode_change_unavailable_outdoor_portable",
            )

        # Switch energy mode if required
        if current_mode != target_mode:
            try:
                success = await self.async_push_data(
                    IndevoltConfig.WRITE_ENERGY_MODE, target_mode
                )
            except (DeviceTimeoutError, DeviceConnectionError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="failed_to_switch_energy_mode",
                ) from err

            if not success:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="failed_to_switch_energy_mode",
                )

            if refresh:
                await self.async_request_refresh()

    async def async_realtime_action(
        self,
        action: IndevoltRealtimeAction,
        power: int = 0,
        target_soc: int = 0,
    ) -> None:
        """Switch mode, execute action, and refresh for real-time control."""

        await self.async_switch_energy_mode(
            IndevoltEnergyMode.REAL_TIME_CONTROL, refresh=False
        )

        success = False

        match action:
            case IndevoltRealtimeAction.CHARGE:
                success = await self.api.charge(power, target_soc)
            case IndevoltRealtimeAction.DISCHARGE:
                success = await self.api.discharge(power, target_soc)
            case IndevoltRealtimeAction.STOP:
                success = await self.api.stop()

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="failed_to_execute_realtime_action",
            )

        await self.async_request_refresh()

    def get_emergency_soc(self) -> int:
        """Get the emergency SOC value."""
        return int(self.data[IndevoltConfig.READ_DISCHARGE_LIMIT])
