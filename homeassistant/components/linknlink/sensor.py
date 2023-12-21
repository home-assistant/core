"""Support for linknlink sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LinknLinkEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="envtemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="envhumid",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the linknlink sensor."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    sensors = [LinknLinkSensor(device, description) for description in SENSOR_TYPES]
    async_add_entities(sensors)


class LinknLinkSensor(LinknLinkEntity, SensorEntity):
    """Representation of a linknlink sensor."""

    _attr_has_entity_name = True

    def __init__(self, device, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self.entity_description = description

        self._attr_native_value = self._coordinator.data[description.key]
        self._attr_unique_id = f"{device.unique_id}-{description.key}"

    def _update_state(self, data):
        """Update the state of the entity."""
        self._attr_native_value = data[self.entity_description.key]
