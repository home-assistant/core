"""Support for ISY994 sensors."""
from typing import Callable

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.typing import ConfigType

from . import ISY994_NODES
from .const import _LOGGER, UOM_FRIENDLY_NAME, UOM_TO_STATES
from .entity import ISYNodeEntity


def setup_platform(
    hass, config: ConfigType, add_entities: Callable[[list], None], discovery_info=None
):
    """Set up the ISY994 sensor platform."""
    devices = []

    for node in hass.data[ISY994_NODES][SENSOR]:
        _LOGGER.debug("Loading %s", node.name)
        devices.append(ISYSensorEntity(node))

    add_entities(devices)


class ISYSensorEntity(ISYNodeEntity):
    """Representation of an ISY994 sensor device."""

    @property
    def raw_unit_of_measurement(self) -> str:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        uom = self._node.uom

        # Backwards compatibility for ISYv4 Firmware:
        if isinstance(uom, list):
            return UOM_FRIENDLY_NAME.get(uom[0], uom[0])
        return UOM_FRIENDLY_NAME.get(uom)

    @property
    def state(self) -> str:
        """Get the state of the ISY994 sensor device."""
        if self.value == ISY_VALUE_UNKNOWN:
            return STATE_UNKNOWN

        uom = self._node.uom
        # Backwards compatibility for ISYv4 Firmware:
        if isinstance(uom, list):
            uom = uom[0]
        if not uom:
            return STATE_UNKNOWN

        states = UOM_TO_STATES.get(uom)
        if states and states.get(self.value):
            return states.get(self.value)
        if self._node.prec and int(self._node.prec) != 0:
            str_val = str(self.value)
            int_prec = int(self._node.prec)
            decimal_part = str_val[-int_prec:]
            whole_part = str_val[: len(str_val) - int_prec]
            val = float(f"{whole_part}.{decimal_part}")
            raw_units = self.raw_unit_of_measurement
            if raw_units in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
                val = self.hass.config.units.temperature(val, raw_units)
            return val
        return self.value

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement for the ISY994 sensor device."""
        raw_units = self.raw_unit_of_measurement
        if raw_units in (TEMP_FAHRENHEIT, TEMP_CELSIUS):
            return self.hass.config.units.temperature_unit
        return raw_units
