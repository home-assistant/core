"""Support for the Airzone sensors."""
from __future__ import annotations

from typing import Any, Final

from aioairzone.const import AZD_HUMIDITY, AZD_NAME, AZD_TEMP, AZD_TEMP_UNIT, AZD_ZONES

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
from .const import DOMAIN, TEMP_UNIT_LIB_TO_HASS
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
    for system_zone_id, zone_data in coordinator.data[AZD_ZONES].items():
        for description in SENSOR_TYPES:
            if description.key in zone_data:
                sensors.append(
                    AirzoneSensor(
                        coordinator,
                        description,
                        entry,
                        system_zone_id,
                        zone_data,
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
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, system_zone_id, zone_data)
        self._attr_name = f"{zone_data[AZD_NAME]} {description.name}"
        self._attr_unique_id = f"{entry.entry_id}_{system_zone_id}_{description.key}"
        self.entity_description = description

        if description.key == AZD_TEMP:
            self._attr_native_unit_of_measurement = TEMP_UNIT_LIB_TO_HASS.get(
                self.get_zone_value(AZD_TEMP_UNIT)
            )

    @property
    def native_value(self):
        """Return the state."""
        return self.get_zone_value(self.entity_description.key)
