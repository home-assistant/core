"""
homeassistant.components.sensor.apcupsd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides a sensor to track various status aspects of a UPS.
"""
import logging

from homeassistant.core import JobPriority
from homeassistant.const import TEMP_CELCIUS
from homeassistant.helpers.entity import Entity
from homeassistant.components import apcupsd


DEPENDENCIES = [apcupsd.DOMAIN]

DEFAULT_NAME = "UPS Status"

SPECIFIC_UNITS = {
    "ITEMP": TEMP_CELCIUS
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """
    Ensure that the 'type' config value has been set and use a specific unit
    of measurement if required.
    """
    typ = config.get(apcupsd.CONF_TYPE)
    if typ is None:
        _LOGGER.error(
            "You must include a '%s' when configuring an APCUPSd sensor.",
            apcupsd.CONF_TYPE)
        return
    typ = typ.upper()

    # Get a status reading from APCUPSd and check whether the user provided
    # 'type' is present in the output. If we're not able to check, then assume
    # the user knows what they're doing.
    # pylint: disable=broad-except
    status = None
    try:
        status = apcupsd.GET_STATUS()
        if typ not in status:
            _LOGGER.error(
                "Specified '%s' of '%s' does not appear in the APCUPSd status "
                "output.", apcupsd.CONF_TYPE, typ)
            return
    except Exception as exc:
        _LOGGER.warning(
            "Unable to fetch initial value from ACPUPSd to check that '%s' is "
            "a supported '%s': %s", typ, apcupsd.CONF_TYPE, exc)
    unit = SPECIFIC_UNITS.get(typ)
    add_entities((
        Sensor(hass, config, unit=unit, initial_status=status),
    ))


def infer_unit(value):
    """
    If the value ends with any of the units from ALL_UNITS, split the unit
    off the end of the value and return the value, unit tuple pair. Else return
    the original value and None as the unit.
    """
    from apcaccess.status import ALL_UNITS
    for unit in ALL_UNITS:
        if value.endswith(unit):
            return value[:-len(unit)], unit
    return value, None


class Sensor(Entity):
    """ Generic sensor entity for APCUPSd status values. """
    def __init__(self, hass, config, unit=None, initial_status=None):
        self._config = config
        self._unit = unit
        self._state = None
        self._inferred_unit = None
        if initial_status is None:
            hass.pool.add_job(
                JobPriority.EVENT_STATE, (self.update_ha_state, True))
        else:
            self._update_from_status(initial_status)

    @property
    def name(self):
        return self._config.get("name", DEFAULT_NAME)

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        if self._unit is None:
            return self._inferred_unit
        return self._unit

    def update(self):
        """ Get the latest status and use it to update our sensor state. """
        self._update_from_status(apcupsd.GET_STATUS())

    def _update_from_status(self, status):
        """ Set state and infer unit from status. """
        key = self._config[apcupsd.CONF_TYPE].upper()
        self._state, self._inferred_unit = infer_unit(status[key])
