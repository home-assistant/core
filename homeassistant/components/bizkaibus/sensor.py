"""Support for Bizkaibus, Biscay (Basque Country, Spain) Bus service."""

from __future__ import annotations

from contextlib import suppress

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTime


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
            self._attr_native_value = "self.data.info[0][ATTR_DUE_IN]"
