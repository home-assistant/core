"""Support for Ripple sensors."""
from __future__ import annotations

from datetime import timedelta

from pyripple import get_balance
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DEFAULT_NAME = "Ripple Balance"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ripple.com sensors."""
    address = config.get(CONF_ADDRESS)
    name = config.get(CONF_NAME)

    add_entities([RippleSensor(name, address)], True)


class RippleSensor(SensorEntity):
    """Representation of an Ripple.com sensor."""

    _attr_attribution = "Data provided by ripple.com"

    def __init__(self, name, address):
        """Initialize the sensor."""
        self._name = name
        self.address = address
        self._state = None
        self._unit_of_measurement = "XRP"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    def update(self) -> None:
        """Get the latest state of the sensor."""
        if (balance := get_balance(self.address)) is not None:
            self._state = balance
