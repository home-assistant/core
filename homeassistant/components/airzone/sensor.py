"""Support for the Airzone sensors."""
from __future__ import annotations

from typing import Final

from aioairzone.const import AZD_HUMIDITY, AZD_NAME, AZD_TEMP, AZD_ZONES

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneEntity
from .const import DOMAIN
from .coordinator import AirzoneUpdateCoordinator

SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        device_class=DEVICE_CLASS_TEMPERATURE,
        key=AZD_TEMP,
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        device_class=DEVICE_CLASS_HUMIDITY,
        key=AZD_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Airzone sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for zone_id, zone_data in coordinator.data[AZD_ZONES].items():
        zone_name = zone_data[AZD_NAME]

        for description in SENSOR_TYPES:
            if description.key in zone_data:
                sensors.append(
                    AirzoneSensor(
                        coordinator,
                        description,
                        entry,
                        zone_id,
                        zone_name,
                    )
                )

    async_add_entities(sensors)


class AirzoneSensor(AirzoneEntity, SensorEntity):
    """Define an Airzone sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, system_zone_id, zone_name)
        self._attr_name = f"{zone_name} {description.name}"
        self._attr_unique_id = f"{entry.entry_id}_{system_zone_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self):
        """Return the state."""
        value = None
        if self.system_zone_id in self.coordinator.data[AZD_ZONES]:
            zone = self.coordinator.data[AZD_ZONES][self.system_zone_id]
            if self.entity_description.key in zone:
                value = zone[self.entity_description.key]
        return value
