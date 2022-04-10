"""Support for myStrom switches/plugs sensors."""
from __future__ import annotations

from contextlib import suppress
import logging

from pymystrom.exceptions import MyStromConnectionError
from pymystrom.switch import MyStromSwitch as _MyStromSwitch
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_NAME, POWER_WATT, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import convert

DEFAULT_NAME = "myStrom Switch"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the myStrom switch/plug integration."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    try:
        plug = _MyStromSwitch(host)
        await plug.get_state()
    except MyStromConnectionError as err:
        _LOGGER.error("No route to myStrom plug: %s", host)
        raise PlatformNotReady() from err

    entities: list[Entity] = []
    entities.append(MyStromPowerSensor(plug, name))
    entities.append(MyStromTemperatureSensor(plug, name))
    async_add_entities(entities)


class MyStromPowerSensor(SensorEntity):
    """Representation of a MySwitch Power Sensor."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = POWER_WATT

    def __init__(self, plug: _MyStromSwitch, name) -> None:
        """Initialize the sensor."""
        self._plug = plug
        self._attr_name = f"{name} Power"
        self._attr_unique_id = f"{plug.mac}.power"
        self.entity_id = f"sensor.{plug.mac}.power"

    async def async_update(self):
        """Update the state."""
        with suppress(KeyError, ValueError):
            await self._plug.get_state()
            self._attr_native_value = convert(self._plug.consumption, float)


class MyStromTemperatureSensor(SensorEntity):
    """Representation of a MySwitch Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    def __init__(self, plug: _MyStromSwitch, name) -> None:
        """Initialize the sensor."""
        self._plug = plug
        self._attr_name = f"{name} Temperature"
        self._attr_unique_id = f"{plug.mac}.temperature"
        self.entity_id = f"sensor.{plug.mac}.temperature"

    async def async_update(self):
        """Update the state."""
        with suppress(KeyError, ValueError):
            await self._plug.get_state()
            self._attr_native_value = convert(self._plug.temperature, float)
