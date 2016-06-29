"""
Provides a sensor to track various status aspects of a UPS.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.apcupsd/
"""
import logging

from homeassistant.components import apcupsd
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DEPENDENCIES = [apcupsd.DOMAIN]
DEFAULT_NAME = "UPS Status"
SPECIFIC_UNITS = {
    "ITEMP": TEMP_CELSIUS
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the APCUPSd sensor."""
    typ = config.get(apcupsd.CONF_TYPE)
    if typ is None:
        _LOGGER.error(
            "You must include a '%s' when configuring an APCUPSd sensor.",
            apcupsd.CONF_TYPE)
        return False
    typ = typ.upper()

    if typ not in apcupsd.DATA.status:
        _LOGGER.error(
            "Specified '%s' of '%s' does not appear in the APCUPSd status "
            "output.", apcupsd.CONF_TYPE, typ)
        return False

    add_entities((
        Sensor(config, apcupsd.DATA, unit=SPECIFIC_UNITS.get(typ)),
    ))


def infer_unit(value):
    """If the value ends with any of the units from ALL_UNITS.

    Split the unit off the end of the value and return the value, unit tuple
    pair. Else return the original value and None as the unit.
    """
    from apcaccess.status import ALL_UNITS
    for unit in ALL_UNITS:
        if value.endswith(unit):
            return value[:-len(unit)], unit
    return value, None


class Sensor(Entity):
    """Representation of a sensor entity for APCUPSd status values."""

    def __init__(self, config, data, unit=None):
        """Initialize the sensor."""
        self._config = config
        self._unit = unit
        self._data = data
        self._inferred_unit = None
        self.update()

    @property
    def name(self):
        """Return the name of the UPS sensor."""
        return self._config.get("name", DEFAULT_NAME)

    @property
    def state(self):
        """Return true if the UPS is online, else False."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self._unit is None:
            return self._inferred_unit
        return self._unit

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        key = self._config[apcupsd.CONF_TYPE].upper()
        self._state, self._inferred_unit = infer_unit(self._data.status[key])
