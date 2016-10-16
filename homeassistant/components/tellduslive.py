"""
Support for Telldus Live.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tellduslive/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

DOMAIN = 'tellduslive'

REQUIREMENTS = ['tellive-py==0.5.2']

_LOGGER = logging.getLogger(__name__)

CONF_PUBLIC_KEY = 'public_key'
CONF_PRIVATE_KEY = 'private_key'
CONF_TOKEN = 'token'
CONF_TOKEN_SECRET = 'token_secret'

MIN_TIME_BETWEEN_SWITCH_UPDATES = timedelta(minutes=1)
MIN_TIME_BETWEEN_SENSOR_UPDATES = timedelta(minutes=5)

NETWORK = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PUBLIC_KEY): cv.string,
        vol.Required(CONF_PRIVATE_KEY): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_TOKEN_SECRET): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the Telldus Live component."""
    # fixme: aquire app key and provide authentication using username+password

    global NETWORK
    NETWORK = TelldusLiveData(hass, config)

    if not NETWORK.validate_session():
        _LOGGER.error(
            "Authentication Error: "
            "Please make sure you have configured your keys "
            "that can be aquired from https://api.telldus.com/keys/index")
        return False

    NETWORK.discover()

    return True


@Throttle(MIN_TIME_BETWEEN_SWITCH_UPDATES)
def request_switches():
    """Make request to online service."""
    _LOGGER.debug("Updating switches from Telldus Live")
    switches = NETWORK.request('devices/list')
    # Filter out any group of switches.
    if switches and 'device' in switches:
        return {switch["id"]: switch for switch in switches['device']
                if switch["type"] == "device"}
    return None


@Throttle(MIN_TIME_BETWEEN_SENSOR_UPDATES)
def request_sensors():
    """Make request to online service."""
    _LOGGER.debug("Updating sensors from Telldus Live")
    units = NETWORK.request('sensors/list')
    # One unit can contain many sensors.
    if units and 'sensor' in units:
        return {unit['id']+sensor['name']: dict(unit, data=sensor)
                for unit in units['sensor']
                for sensor in unit['data']}
    return None


class TelldusLiveData(object):
    """Get the latest data and update the states."""

    def __init__(self, hass, config):
        """Initialize the Tellus data object."""
        public_key = config[DOMAIN].get(CONF_PUBLIC_KEY)
        private_key = config[DOMAIN].get(CONF_PRIVATE_KEY)
        token = config[DOMAIN].get(CONF_TOKEN)
        token_secret = config[DOMAIN].get(CONF_TOKEN_SECRET)

        from tellive.client import LiveClient

        self._switches = {}
        self._sensors = {}

        self._hass = hass
        self._config = config

        self._client = LiveClient(
            public_key=public_key, private_key=private_key, access_token=token,
            access_secret=token_secret)

    def validate_session(self):
        """Make a dummy request to see if the session is valid."""
        response = self.request("user/profile")
        return response and 'email' in response

    def discover(self):
        """Update states, will trigger discover."""
        self.update_sensors()
        self.update_switches()

    def _discover(self, found_devices, component_name):
        """Send discovery event if component not yet discovered."""
        if not len(found_devices):
            return

        _LOGGER.info("discovered %d new %s devices",
                     len(found_devices), component_name)

        discovery.load_platform(self._hass, component_name, DOMAIN,
                                found_devices, self._config)

    def request(self, what, **params):
        """Send a request to the Tellstick Live API."""
        from tellive.live import const

        supported_methods = const.TELLSTICK_TURNON \
            | const.TELLSTICK_TURNOFF \
            | const.TELLSTICK_TOGGLE \

        # Tellstick device methods not yet supported
        #   | const.TELLSTICK_BELL \
        #   | const.TELLSTICK_DIM \
        #   | const.TELLSTICK_LEARN \
        #   | const.TELLSTICK_EXECUTE \
        #   | const.TELLSTICK_UP \
        #   | const.TELLSTICK_DOWN \
        #   | const.TELLSTICK_STOP

        default_params = {'supportedMethods': supported_methods,
                          'includeValues': 1,
                          'includeScale': 1,
                          'includeIgnored': 0}
        params.update(default_params)

        # room for improvement: the telllive library doesn't seem to
        # re-use sessions, instead it opens a new session for each request
        # this needs to be fixed

        try:
            response = self._client.request(what, params)
            _LOGGER.debug("got response %s", response)
            return response
        except (ConnectionError, TimeoutError, OSError) as error:
            _LOGGER.error("failed to make request to Tellduslive servers: %s",
                          error)
            return None

    def update_devices(self, local_devices, remote_devices, component_name):
        """Update local device list and discover new devices."""
        if remote_devices is None:
            return local_devices

        remote_ids = remote_devices.keys()
        local_ids = local_devices.keys()

        added_devices = list(remote_ids - local_ids)
        self._discover(added_devices,
                       component_name)

        removed_devices = list(local_ids - remote_ids)
        remote_devices.update({id: dict(local_devices[id], offline=True)
                               for id in removed_devices})

        return remote_devices

    def update_sensors(self):
        """Update local list of sensors."""
        self._sensors = self.update_devices(
            self._sensors, request_sensors(), 'sensor')

    def update_switches(self):
        """Update local list of switches."""
        self._switches = self.update_devices(
            self._switches, request_switches(), 'switch')

    def _check_request(self, what, **params):
        """Make request, check result if successful."""
        response = self.request(what, **params)
        return response and response.get('status') == 'success'

    def get_switch(self, switch_id):
        """Return the switch representation."""
        return self._switches[switch_id]

    def get_sensor(self, sensor_id):
        """Return the sensor representation."""
        return self._sensors[sensor_id]

    def turn_switch_on(self, switch_id):
        """Turn switch off."""
        if self._check_request('device/turnOn', id=switch_id):
            from tellive.live import const
            self.get_switch(switch_id)['state'] = const.TELLSTICK_TURNON

    def turn_switch_off(self, switch_id):
        """Turn switch on."""
        if self._check_request('device/turnOff', id=switch_id):
            from tellive.live import const
            self.get_switch(switch_id)['state'] = const.TELLSTICK_TURNOFF
