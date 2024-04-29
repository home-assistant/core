"""Support for Hydrawise sprinkler sensors."""

from __future__ import annotations

from datetime import datetime

from pydrawise.schema import Zone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_cycle",
        translation_key="next_cycle",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="watering_time",
        translation_key="watering_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]
TWO_YEAR_SECONDS = 60 * 60 * 24 * 365 * 2
WATERING_TIME_ICON = "mdi:water-pump"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hydrawise sensor platform."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        HydrawiseSensor(coordinator, description, controller, zone)
        for controller in coordinator.data.controllers.values()
        for zone in controller.zones
        for description in SENSOR_TYPES
    )


class HydrawiseSensor(HydrawiseEntity, SensorEntity):
    """A sensor implementation for Hydrawise device."""

    zone: Zone

    def _update_attrs(self) -> None:
        """Update state attributes."""
        if self.entity_description.key == "watering_time":
            if (current_run := self.zone.scheduled_runs.current_run) is not None:
                self._attr_native_value = int(
                    current_run.remaining_time.total_seconds() / 60
                )
            else:
                self._attr_native_value = 0
        elif self.entity_description.key == "next_cycle":
            if (next_run := self.zone.scheduled_runs.next_run) is not None:
                self._attr_native_value = dt_util.as_utc(next_run.start_time)
            else:
                self._attr_native_value = datetime.max.replace(tzinfo=dt_util.UTC)
