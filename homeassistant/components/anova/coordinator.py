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


class AnovaCoordinator(DataUpdateCoordinator[APCUpdate | None]):
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
        # Owned by the coordinator, not the number entities, so it's seeded
        # from the device's own state (see _handle_device_update) regardless
        # of entity setup ordering.
        self.pending_target_temperature: float | None = None
        self.pending_cook_time_seconds: int | None = None
        self.anova_device.set_update_listener(self._handle_device_update)
        if (last_update := anova_device.last_update) is not None:
            self._handle_device_update(last_update)

    def _handle_device_update(self, update: APCUpdate) -> None:
        """Seed the pending target temperature/timer on first data, then propagate."""
        if self.pending_target_temperature is None:
            self.pending_target_temperature = update.sensor.target_temperature
        if self.pending_cook_time_seconds is None:
            self.pending_cook_time_seconds = update.sensor.cook_time
        self.async_set_updated_data(update)
