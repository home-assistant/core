"""
Toon van Eneco Support.

This provides a component for the rebranded Quby thermostat as provided by
Eneco.
"""
import logging
from datetime import datetime, timedelta
import voluptuous as vol

# Import the device class from the component that you want to support
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD)
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

# Home Assistant depends on 3rd party packages for API specific code.
REQUIREMENTS = ['toonlib==1.0.2']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

DOMAIN = 'toon'
TOON_HANDLE = 'toon_handle'
CONF_GAS = 'gas'
DEFAULT_GAS = True
CONF_SOLAR = 'solar'
DEFAULT_SOLAR = False

# Validation of the user's configuration
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_GAS, default=DEFAULT_GAS): cv.boolean,
        vol.Optional(CONF_SOLAR, default=DEFAULT_SOLAR): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup toon."""
    from toonlib import InvalidCredentials
    gas = config['toon']['gas']
    solar = config['toon']['solar']

    try:
        hass.data[TOON_HANDLE] = ToonDataStore(config['toon']['username'],
                                               config['toon']['password'],
                                               gas,
                                               solar)
    except InvalidCredentials:
        return False

    # Load all platforms
    for platform in ('climate', 'sensor', 'switch'):
        load_platform(hass, platform, DOMAIN, {}, config)

    # Initialization successfull
    return True


class ToonDataStore:
    """An object to store the toon data."""

    def __init__(self, username, password, gas=DEFAULT_GAS,
                 solar=DEFAULT_SOLAR):
        """Initialize toon."""
        from toonlib import Toon

        # Creating the class

        toon = Toon(username, password)

        self.toon = toon
        self.gas = gas
        self.solar = solar
        self.data = {}

        self.last_update = datetime.min
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update toon data."""
        self.last_update = datetime.now()

        self.data['power_current'] = self.toon.power.value
        self.data['power_today'] = round(
            (float(self.toon.power.daily_usage) +
             float(self.toon.power.daily_usage_low)) / 1000, 2)
        self.data['temp'] = self.toon.temperature

        if self.toon.thermostat_state:
            self.data['state'] = self.toon.thermostat_state.name
        else:
            self.data['state'] = 'Manual'

        self.data['setpoint'] = float(
            self.toon.thermostat_info.current_set_point) / 100
        self.data['gas_current'] = self.toon.gas.value
        self.data['gas_today'] = round(float(self.toon.gas.daily_usage) /
                                       1000, 2)

        for plug in self.toon.smartplugs:
            self.data[plug.name] = {'current_power': plug.current_usage,
                                    'today_energy': round(
                                        float(plug.daily_usage) / 1000, 2),
                                    'current_state': plug.current_state,
                                    'is_connected': plug.is_connected}

        self.data['solar_maximum'] = self.toon.solar.maximum
        self.data['solar_produced'] = self.toon.solar.produced
        self.data['solar_value'] = self.toon.solar.value
        self.data['solar_average_produced'] = self.toon.solar.average_produced
        self.data['solar_meter_reading_low_produced'] = \
            self.toon.solar.meter_reading_low_produced
        self.data['solar_meter_reading_produced'] = \
            self.toon.solar.meter_reading_produced
        self.data['solar_daily_cost_produced'] = \
            self.toon.solar.daily_cost_produced

        for detector in self.toon.smokedetectors:
            value = '{}_smoke_detector'.format(detector.name)
            self.data[value] = {'smoke_detector': detector.battery_level,
                                'device_type': detector.device_type,
                                'is_connected': detector.is_connected,
                                'last_connected_change':
                                detector.last_connected_change}

    def set_state(self, state):
        """Push a new state to the Toon unit."""
        self.toon.thermostat_state = state

    def set_temp(self, temp):
        """Push a new temperature to the Toon unit."""
        self.toon.thermostat = temp

    def get_data(self, data_id, plug_name=None):
        """Get the cached data."""
        data = {'error': 'no data'}
        if plug_name:
            if data_id in self.data[plug_name]:
                data = self.data[plug_name][data_id]
        else:
            if data_id in self.data:
                data = self.data[data_id]
        return data
