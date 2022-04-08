"""Support for Bizkaibus, Biscay (Basque Country, Spain) Bus service."""
from __future__ import annotations

from contextlib import suppress

from bizkaibus.bizkaibus import BizkaibusData
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, TIME_MINUTES
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

ATTR_DUE_IN = "Due in"

CONF_STOP_ID = "stopid"
CONF_ROUTE = "route"

DEFAULT_NAME = "Next bus"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Required(CONF_ROUTE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Bizkaibus public transport sensor."""
    name = config[CONF_NAME]
    stop = config[CONF_STOP_ID]
    route = config[CONF_ROUTE]

    data = Bizkaibus(stop, route)
    add_entities([BizkaibusSensor(data, name)], True)


class BizkaibusSensor(SensorEntity):
    """The class for handling the data."""

    _attr_native_unit_of_measurement = TIME_MINUTES

    def __init__(self, data, name):
        """Initialize the sensor."""
        self.data = data
        self._attr_name = name

    def update(self):
        """Get the latest data from the webservice."""
        self.data.update()
        with suppress(TypeError):
            self._attr_native_value = self.data.info[0][ATTR_DUE_IN]


class Bizkaibus:
    """The class for handling the data retrieval."""

    def __init__(self, stop, route):
        """Initialize the data object."""
        self.stop = stop
        self.route = route
        self.info = None

    def update(self):
        """Retrieve the information from API."""
        bridge = BizkaibusData(self.stop, self.route)
        bridge.getNextBus()
        self.info = bridge.info
