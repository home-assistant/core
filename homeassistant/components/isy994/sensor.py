"""Support for ISY994 sensors."""
from typing import Callable

from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.typing import ConfigType

from . import ISY994_NODES, ISY994_WEATHER, ISYDevice
from .const import _LOGGER, UOM_FRIENDLY_NAME, UOM_TO_STATES


def setup_platform(
    hass, config: ConfigType, add_entities: Callable[[list], None], discovery_info=None
):
    """Set up the ISY994 sensor platform."""
    devices = []

    for node in hass.data[ISY994_NODES][SENSOR]:
        _LOGGER.debug("Loading %s", node.name)
        devices.append(ISYSensorDevice(node))

    for node in hass.data[ISY994_WEATHER]:
        devices.append(ISYWeatherDevice(node))

    add_entities(devices)


class ISYSensorDevice(ISYDevice):
    """Representation of an ISY994 sensor device."""

    @property
    def raw_unit_of_measurement(self) -> str:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        if len(self._node.uom) == 1:
            if self._node.uom[0] in UOM_FRIENDLY_NAME:
                friendly_name = UOM_FRIENDLY_NAME.get(self._node.uom[0])
                if friendly_name in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
                    friendly_name = self.hass.config.units.temperature_unit
                return friendly_name
            return self._node.uom[0]
        return None

    @property
    def state(self) -> str:
        """Get the state of the ISY994 sensor device."""
        if self.is_unknown():
            return None

        if len(self._node.uom) == 1:
            if self._node.uom[0] in UOM_TO_STATES:
                states = UOM_TO_STATES.get(self._node.uom[0])
                # TEMPORARY: Cast value to int until PyISYv2.
                if int(self.value) in states:
                    return states.get(int(self.value))
            elif self._node.prec and self._node.prec != [0]:
                str_val = str(self.value)
                int_prec = int(self._node.prec)
                decimal_part = str_val[-int_prec:]
                whole_part = str_val[: len(str_val) - int_prec]
                val = float(f"{whole_part}.{decimal_part}")
                raw_units = self.raw_unit_of_measurement
                if raw_units in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
                    val = self.hass.config.units.temperature(val, raw_units)

                return str(val)
            else:
                return self.value

        return None

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement for the ISY994 sensor device."""
        raw_units = self.raw_unit_of_measurement
        if raw_units in (TEMP_FAHRENHEIT, TEMP_CELSIUS):
            return self.hass.config.units.temperature_unit
        return raw_units


class ISYWeatherDevice(ISYDevice):
    """Representation of an ISY994 weather device."""

    @property
    def raw_units(self) -> str:
        """Return the raw unit of measurement."""
        if self._node.uom == "F":
            return TEMP_FAHRENHEIT
        if self._node.uom == "C":
            return TEMP_CELSIUS
        return self._node.uom

    @property
    def state(self) -> object:
        """Return the value of the node."""
        # pylint: disable=protected-access
        val = self._node.status._val
        raw_units = self._node.uom

        if raw_units in [TEMP_CELSIUS, TEMP_FAHRENHEIT]:
            return self.hass.config.units.temperature(val, raw_units)
        return val

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement for the node."""
        raw_units = self.raw_units

        if raw_units in [TEMP_CELSIUS, TEMP_FAHRENHEIT]:
            return self.hass.config.units.temperature_unit
        return raw_units
