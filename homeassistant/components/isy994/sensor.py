"""Support for ISY994 sensors."""
import logging
from typing import Callable, Optional

from homeassistant.components.sensor import DOMAIN
from homeassistant.const import (
    CONF_DEVICE_CLASS, CONF_ICON, CONF_ID, CONF_NAME, CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.typing import ConfigType, Dict

from . import ISYDevice
from .const import (
    ISY994_NODES, ISY994_VARIABLES, ISY994_WEATHER, UOM_FRIENDLY_NAME,
    UOM_TO_STATES)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config: ConfigType,
                               async_add_entities: Callable[[list], None],
                               discovery_info=None):
    """Set up the ISY994 sensor platform."""
    devices = []

    for node in hass.data[ISY994_NODES][DOMAIN]:
        _LOGGER.debug("Loading %s", node.name)
        devices.append(ISYSensorDevice(node))

    for node in hass.data[ISY994_WEATHER]:
        devices.append(ISYWeatherDevice(node))

    for vcfg, vname, vobj in hass.data[ISY994_VARIABLES][DOMAIN]:
        devices.append(ISYSensorVariableDevice(vcfg, vname, vobj))

    async_add_entities(devices)


class ISYSensorDevice(ISYDevice):
    """Representation of an ISY994 sensor device."""

    @property
    def raw_unit_of_measurement(self) -> str:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        uom = self._node.uom
        if isinstance(uom, list):
            uom = uom[0]

        if uom in UOM_FRIENDLY_NAME:
            friendly_name = UOM_FRIENDLY_NAME.get(uom)
            if friendly_name in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
                friendly_name = self.hass.config.units.temperature_unit
            return friendly_name
        return uom

    @property
    def state(self) -> str:
        """Get the state of the ISY994 sensor device."""
        if self.is_unknown():
            return None

        if len(self._node.uom) == 1:
            if self._node.uom[0] in UOM_TO_STATES:
                states = UOM_TO_STATES.get(self._node.uom[0])
                if self.value in states:
                    return states.get(self.value)
            elif self._node.prec and self._node.prec != [0]:
                str_val = str(self.value)
                int_prec = int(self._node.prec)
                decimal_part = str_val[-int_prec:]
                whole_part = str_val[:len(str_val) - int_prec]
                val = float('{}.{}'.format(whole_part, decimal_part))
                raw_units = self.raw_unit_of_measurement
                if raw_units in (
                        TEMP_CELSIUS, TEMP_FAHRENHEIT):
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


class ISYSensorVariableDevice(ISYDevice):
    """Representation of an ISY994 variable as a sensor device."""

    def __init__(self, vcfg: dict, vname: str, vobj: object) -> None:
        """Initialize the ISY994 binary sensor program."""
        super().__init__(vobj)
        self._config = vcfg
        self._name = vcfg.get(CONF_NAME, vname)
        self._vtype = vcfg.get(CONF_TYPE)
        self._vid = vcfg.get(CONF_ID)
        self._change_handler = None
        self._init_change_handler = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to the node change events."""
        self._change_handler = self._node.val.subscribe(
            'changed', self.on_update)
        self._init_change_handler = self._node.init.subscribe(
            'changed', self.on_update)

    @property
    def state(self) -> str:
        """Get the state of the ISY994 variable sensor device."""
        if self.is_unknown():
            return None
        return self.value

    @property
    def value(self) -> int:
        """Get the current value of the device."""
        return int(self._node.val)

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        attr = {}
        attr['init_value'] = int(self._node.init)
        return attr

    @property
    def icon(self):
        """Return the icon."""
        return self._config.get(CONF_ICON)

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class of the sensor."""
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._config.get(CONF_UNIT_OF_MEASUREMENT)


class ISYWeatherDevice(ISYDevice):
    """Representation of an ISY994 weather device."""

    @property
    def raw_units(self) -> str:
        """Return the raw unit of measurement."""
        if self._node.uom == 'F':
            return TEMP_FAHRENHEIT
        if self._node.uom == 'C':
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
