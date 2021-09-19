"""Sensor support for Skybell Doorbells."""
from __future__ import annotations

from datetime import timedelta

from skybellpy.device import SkybellDevice
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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import DOMAIN, SkybellEntity
from .const import DATA_COORDINATOR, DATA_DEVICES

SCAN_INTERVAL = timedelta(seconds=30)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="chime_level",
        name="Chime Level",
        icon="mdi:bell-ring",
    ),
)

# Deprecated in Home Assistant 2021.10
PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
                vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
                    cv.ensure_list, [vol.In(SENSOR_TYPES)]
                ),
            }
        )
    )
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell sensor."""
    skybell = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        SkybellSensor(skybell[DATA_COORDINATOR], device, description, entry.entry_id)
        for device in skybell[DATA_DEVICES]
        for description in SENSOR_TYPES
    ]

    async_add_entities(sensors)


class SkybellSensor(SkybellEntity, SensorEntity):
    """A sensor implementation for Skybell devices."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: SkybellDevice,
        description: SensorEntityDescription,
        server_unique_id: str,
    ) -> None:
        """Initialize a sensor for a Skybell device."""
        super().__init__(coordinator, device, description, server_unique_id)
        self.entity_description = description
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{server_unique_id}/{description.key}"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._device.outdoor_chime_level
