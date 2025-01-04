"""Support for Bizkaibus, Biscay (Basque Country, Spain) Bus service."""

from __future__ import annotations

from contextlib import suppress

from bizkaibus.bizkaibus import BizkaibusData

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_DUE_IN, CONF_STOP_ID


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Bizkaibus public transport sensor."""
    stop = config[CONF_STOP_ID]

    data = Bizkaibus(stop)
    add_entities([BizkaibusSensor(data, "hola")], True)


class BizkaibusSensor(SensorEntity):
    """The class for handling the data."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_should_poll = True

    def __init__(self, data, name) -> None:
        """Initialize the sensor."""
        self.data = data
        self._attr_name = name

    def update(self) -> None:
        """Get the latest data from the webservice."""
        self.data.update()
        with suppress(TypeError):
            self._attr_native_value = self.data.info[0][ATTR_DUE_IN]


class Bizkaibus:
    """The class for handling the data retrieval."""

    def __init__(self, stop) -> None:
        """Initialize the data object."""
        self.stop = stop
        self.info = None

    def update(self):
        """Retrieve the information from API."""
        bridge = BizkaibusData(self.stop)
        bridge.getNextBus()
        self.info = bridge.info
