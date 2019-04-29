"""Support for Essent API."""
from datetime import timedelta

from pyessent import PyEssent
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, ENERGY_KILO_WATT_HOUR)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

SCAN_INTERVAL = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Essent platform."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    devices = []
    for meter in EssentBase(username, password).retrieve_meters():
        for tariff in ['L', 'N', 'H']:
            try:
                devices.append(EssentMeter(username, password, meter, tariff))
            except KeyError:
                # Don't add devices for non-existing meter/tariff combinations
                pass  

    add_devices(devices, True)


class EssentBase():
    """Essent Base."""

    def __init__(self, username, password):
        """Initialize the Essent API."""
        self._essent = PyEssent(username, password)

    def get_session(self):
        """Return the active session."""
        return self._essent

    def retrieve_meters(self):
        """Retrieve the IDs of the meters used by Essent."""
        return self._essent.get_EANs()


class EssentMeter(Entity):
    """Representation of Essent measurements."""

    def __init__(self, username, password, meter, tariff):
        """Initialize the sensor."""
        self._state = None
        self._username = username
        self._password = password
        self._meter = meter
        self._tariff = tariff
        self._meter_type = None
        self._meter_unit = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Essent {} ({})".format(self._meter_type, self._tariff)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._meter_unit and self._meter_unit.lower() == 'kwh':
            return ENERGY_KILO_WATT_HOUR

        return self._meter_unit

    def update(self):
        """Fetch the energy usage."""
        # Retrieve an authenticated session
        essent = EssentBase(self._username, self._password).get_session()

        # Read the meter
        data = essent.read_meter(self._meter, only_last_meter_reading=True)

        self._meter_type = data['type']
        self._meter_unit = data['values']['LVR'][self._tariff]['unit']

        self._state = next(
            iter(data['values']['LVR'][self._tariff]['records'].values()))
