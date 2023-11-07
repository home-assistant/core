"""Sensor for traffic information."""
from __future__ import annotations

# from homeassistant.helpers.entity_platform import AddEntitiesCallback
# from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sr traffic platform."""
    async_add_entities([TrafficSensor()])


class TrafficSensor(SensorEntity):
    """A class for the Steam account."""

    def __init__(self) -> None:
        """Initialize the sensor."""
        _attr_name = "Example Temperature"
        _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        _attr_device_class = SensorDeviceClass.TEMPERATURE
        _attr_state_class = SensorStateClass.MEASUREMENT

        def update(self) -> None:
            """Fetch new state data for the sensor.

            This is the only method that should fetch new data for Home Assistant.
            """
            self._attr_native_value = 29

        # @property
        # def native_value(self) -> StateType:
        #    """Does stuff."""
        #    return 24
        #    # return "stuff is cool :^)"


#

# """Platform for sensor integration."""
# from __future__ import annotations
#
#
#
# def setup_platform(
#    hass: HomeAssistant,
#    config: ConfigType,
#    add_entities: AddEntitiesCallback,
#    discovery_info: DiscoveryInfoType | None = None
# ) -> None:
#    """Set up the sensor platform."""
#    add_entities([ExampleSensor()])
#
#
# class ExampleSensor(SensorEntity):
#    """Representation of a Sensor."""
#
#    _attr_name = "Example Temperature"
#    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
#    _attr_device_class = SensorDeviceClass.TEMPERATURE
#    _attr_state_class = SensorStateClass.MEASUREMENT
#
#    def update(self) -> None:
#        """Fetch new state data for the sensor.
#
#        This is the only method that should fetch new data for Home Assistant.
#        """
#        self._attr_native_value = 23
