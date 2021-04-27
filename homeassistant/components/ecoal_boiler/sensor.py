"""Allows reading temperatures from ecoal/esterownik.pl controller."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import TEMP_CELSIUS

from . import AVAILABLE_SENSORS, DATA_ECOAL_BOILER


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ecoal sensors."""
    if discovery_info is None:
        return
    devices = []
    ecoal_contr = hass.data[DATA_ECOAL_BOILER]
    for sensor_id in discovery_info:
        name = AVAILABLE_SENSORS[sensor_id]
        devices.append(EcoalTempSensor(ecoal_contr, name, sensor_id))
    add_entities(devices, True)


class EcoalTempSensor(SensorEntity):
    """Representation of a temperature sensor using ecoal status data."""

    def __init__(self, ecoal_contr, name, status_attr):
        """Initialize the sensor."""
        self._ecoal_contr = ecoal_contr
        self._name = name
        self._status_attr = status_attr
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        # Old values read 0.5 back can still be used
        status = self._ecoal_contr.get_cached_status()
        self._state = getattr(status, self._status_attr)
