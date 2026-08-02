"""Support for Anova Coordinators."""

from dataclasses import dataclass
import logging

from anova_wifi import AnovaApi, APCUpdate, APCWifiDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class AnovaData:
    """Data for the Anova integration."""

    api_jwt: str
    coordinators: list[AnovaCoordinator]
    api: AnovaApi


type AnovaConfigEntry = ConfigEntry[AnovaData]


class AnovaCoordinator(DataUpdateCoordinator[APCUpdate]):
    """Anova custom coordinator."""

    config_entry: AnovaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AnovaConfigEntry,
        anova_device: APCWifiDevice,
    ) -> None:
        """Set up Anova Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name="Anova Precision Cooker",
            logger=_LOGGER,
        )
        self.device_unique_id = anova_device.cooker_id
        self.anova_device = anova_device
        self.device_info: DeviceInfo | None = None

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_unique_id)},
            name="Anova Precision Cooker",
            manufacturer="Anova",
            model="Precision Cooker",
        )
        self.sensor_data_set: bool = False
        # The target temperature/timer number entities hold these locally while
        # idle (mirroring the official app - the device itself only applies a
        # target temperature while a cook is already running, see
        # APCWifiDevice.update_running_cook), and read them here so the cook
        # switch's turn_on can start a cook with whatever the user last set.
        # Seeded (once, below) from this device's own last-reported job values
        # (which persist into idle state), or overridden by restored entity
        # state - never a hardcoded default. Seeded on the coordinator itself,
        # tied directly to the device's update_listener, so it's available
        # regardless of entity setup ordering/races.
        self.pending_target_temperature: float | None = None
        self.pending_cook_time_seconds: int | None = None
        self.anova_device.set_update_listener(self._handle_device_update)

    def _handle_device_update(self, update: APCUpdate) -> None:
        """Seed the pending target temperature/timer on first data, then propagate."""
        if self.pending_target_temperature is None:
            self.pending_target_temperature = update.sensor.target_temperature
        if self.pending_cook_time_seconds is None:
            self.pending_cook_time_seconds = update.sensor.cook_time
        self.async_set_updated_data(update)
