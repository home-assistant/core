"""Sensor for Hyundai / Kia Connect integration."""
import logging
from typing import Final

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .const import DOMAIN
from .entity import HyundaiKiaConnectEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key="odometer",
        name="Odometer",
        icon="mdi:speedometer",
    ),
    SensorEntityDescription(
        key="last_updated",
        name="Last Updated",
        icon="mdi:update",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.unique_id]
    entities = []
    for description in SENSOR_DESCRIPTIONS:
        if description.key in coordinator.data.__dict__:
            sensor = HyundaiKiaConnectSensor(coordinator, description)
            entities.append(sensor)
    async_add_entities(entities, True)
    return True


class HyundaiKiaConnectSensor(SensorEntity, HyundaiKiaConnectEntity):
    """Hyundai / Kia Connect sensor class."""

    def __init__(self, coordinator, description: SensorEntityDescription):
        """Initialize the sensor."""
        HyundaiKiaConnectEntity.__init__(self, coordinator)
        self._description = description
        self._key = self._description.key
        self._attr_unique_id = f"{DOMAIN}_{self.coordinator.data.name}_{self._key}"
        self._attr_icon = self._description.icon
        self._attr_name = f"{self.coordinator.data.name} {self._description.name}"
        self._attr_state_class = self._description.state_class
        self._attr_native_unit_of_measurement = (
            self._description.native_unit_of_measurement
        )
        self._attr_device_class = self._description.device_class
        self._attr_native_value = self.coordinator.data.__dict__[self._key]
