"""Sensor support for Skybell Doorbells."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, SkybellEntity
from .coordinator import SkybellDataUpdateCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="chime_level",
        name="Chime Level",
        icon="mdi:bell-ring",
    ),
)

# Deprecated in Home Assistant 2022.4
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell sensor."""
    async_add_entities(
        SkybellSensor(coordinator, description)
        for coordinator in hass.data[DOMAIN][entry.entry_id]
        for description in SENSOR_TYPES
    )


class SkybellSensor(SkybellEntity, SensorEntity):
    """A sensor implementation for Skybell devices."""

    coordinator: SkybellDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SkybellDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a sensor for a Skybell device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{coordinator.device.device_id}_{description.key}"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.device.outdoor_chime_level
