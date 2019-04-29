"""Support for Essent API."""
from datetime import timedelta

from pyessent import PyEssent

from homeassistant.const import ENERGY_KILO_WATT_HOUR, STATE_UNKNOWN
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

DOMAIN = 'essent'

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Essent platform."""
    username = config['username']
    password = config['password']
    for meter in EssentBase(username, password).retrieve_meters():
        for tariff in ['L', 'N', 'H']:
            add_devices([EssentMeter(username, password, meter, tariff)])


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
        self._meter_type = STATE_UNKNOWN
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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch the energy usage."""
        # Retrieve an authenticated session
        essent = EssentBase(self._username, self._password).get_session()

        # Read the meter
        data = essent.read_meter(self._meter, only_last_meter_reading=True)

        self._meter_type = data['type']
        self._meter_unit = data['values']['LVR'][self._tariff]['unit']

        self._state = data['values']['LVR'][self._tariff]['records'][0]
