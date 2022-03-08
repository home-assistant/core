"""Support for the Airzone sensors."""
from __future__ import annotations

from aioairzone.const import AZD_NAME, AZD_ZONES

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneDevice
from .const import DOMAIN, SENSOR_TYPES
from .coordinator import AirzoneUpdateCoordinator


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
                        zone_id,
                        zone_name,
                    )
                )

    async_add_entities(sensors, False)


class AirzoneSensor(AirzoneDevice, SensorEntity):
    """Define an Airzone sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        zone_id: str,
        zone_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, zone_id, zone_name)
        self._attr_name = f"{zone_name} {description.name}"
        self._attr_unique_id = f"{DOMAIN}_{zone_id}_{description.key}"
        self.entity_description = description
        self.zone_id = zone_id

    @property
    def native_value(self):
        """Return the state."""
        value = None
        if self.zone_id in self.coordinator.data[AZD_ZONES]:
            zone = self.coordinator.data[AZD_ZONES][self.zone_id]
            if self.entity_description.key in zone:
                value = zone[self.entity_description.key]
        return value
