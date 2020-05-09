"""Support for ISY994 sensors."""
from typing import Callable, Dict

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    ISY994_NODES,
    ISY994_VARIABLES,
    UOM_DOUBLE_TEMP,
    UOM_FRIENDLY_NAME,
    UOM_INDEX,
    UOM_ON_OFF,
    UOM_TO_STATES,
)
from .entity import ISYEntity, ISYNodeEntity
from .helpers import migrate_old_unique_ids
from .services import async_setup_device_services


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
    async_setup_device_services(hass)


class ISYSensorEntity(ISYNodeEntity):
    """Representation of an ISY994 sensor device."""

    @property
    def raw_unit_of_measurement(self) -> str:
        """Get the raw unit of measurement for the ISY994 sensor device."""
        uom = self._node.uom

        # Backwards compatibility for ISYv4 Firmware:
        if isinstance(uom, list):
            return UOM_FRIENDLY_NAME.get(uom[0], uom[0])
        # Special case for ISY UOM 101 0.5-precision degrees and index units:
        if uom in (UOM_DOUBLE_TEMP, UOM_INDEX, UOM_ON_OFF):
            return uom
        return UOM_FRIENDLY_NAME.get(uom)

    @property
    def state(self) -> str:
        """Get the state of the ISY994 sensor device."""
        value = self._node.status
        if value == ISY_VALUE_UNKNOWN:
            return None

        uom = self.raw_unit_of_measurement
        if (
            uom in [None, UOM_INDEX, UOM_ON_OFF]
            and hasattr(self._node, "formatted")
            and not self._node.formatted == ISY_VALUE_UNKNOWN
        ):
            # Use the ISY-provided formatted value if the UOM is an index-type.
            return self._node.formatted

        states = UOM_TO_STATES.get(uom)
        if states and states.get(value) is not None:
            return states.get(value)

        if self._node.prec != "0":
            int_prec = int(self._node.prec)
            value = round(float(value) / 10 ** int_prec, int_prec)

        if uom in (TEMP_CELSIUS, TEMP_FAHRENHEIT):
            value = self.hass.config.units.temperature(value, uom)
        elif uom == UOM_DOUBLE_TEMP:
            # Special case for ISY UOM 101 0.5-precision degrees unit
            # Assume the same temp unit as Hass. Not reported by ISY.
            value = round(float(value) / 2.0, 1)

        return value

    @property
    def unit_of_measurement(self) -> str:
        """Get the unit of measurement for the ISY994 sensor device."""
        raw_units = self.raw_unit_of_measurement
        if raw_units in (TEMP_FAHRENHEIT, TEMP_CELSIUS, UOM_DOUBLE_TEMP):
            return self.hass.config.units.temperature_unit
        if raw_units in (UOM_INDEX, UOM_ON_OFF):
            return None
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
