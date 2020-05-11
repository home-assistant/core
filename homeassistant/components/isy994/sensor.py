"""Support for ISY994 sensors."""
from typing import Callable, Dict

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_VARIABLES,
    UOM_FRIENDLY_NAME,
    UOM_TO_STATES,
)
from .entity import ISYEntity, ISYNodeEntity
from .helpers import migrate_old_unique_ids


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 sensor platform."""
    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    devices = []

    for node in hass_isy_data[ISY994_NODES][SENSOR]:
        _LOGGER.debug("Loading %s", node.name)
        devices.append(ISYSensorEntity(node))

    for vname, vobj in hass_isy_data[ISY994_VARIABLES]:
        devices.append(ISYSensorVariableEntity(vname, vobj))

    await migrate_old_unique_ids(hass, SENSOR, devices)
    async_add_entities(devices)


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


class ISYSensorVariableEntity(ISYEntity):
    """Representation of an ISY994 variable as a sensor device."""

    def __init__(self, vname: str, vobj: object) -> None:
        """Initialize the ISY994 binary sensor program."""
        super().__init__(vobj)
        self._name = vname

    @property
    def state(self):
        """Return the state of the variable."""
        return self.value

    @property
    def device_state_attributes(self) -> Dict:
        """Get the state attributes for the device."""
        return {"init_value": int(self._node.init)}

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:counter"
