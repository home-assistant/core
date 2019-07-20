"""Support for KEBA charging stations."""
import asyncio
import logging
from keba_kecontact.connection import KebaKeContact

import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'keba'
SUPPORTED_COMPONENTS = ['binary_sensor', 'sensor', "lock"]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional('rfid', default='00845500'): cv.string,
        vol.Optional('failsafe', default=False): cv.boolean,
        vol.Optional('failsafe_timeout', default=30): cv.positive_int,
        vol.Optional('failsafe_fallback', default=6): cv.positive_int,
        vol.Optional('failsafe_persist', default=0): cv.positive_int,
        vol.Optional('refresh_interval', default=5): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)

_SERVICE_MAP = {
    'request_data': 'request_data',
    'set_energy': 'async_set_energy',
    'set_current': 'async_set_current',
    'authorize': 'async_start',
    'deauthorize': 'async_stop',
    'enable': 'async_ena1',
    'disable': 'async_ena0',
    'set_failsafe': 'async_set_failsafe'
}


async def async_setup(hass, config):
    """Check connectivity and version of KEBA charging station."""
    host = config[DOMAIN][CONF_HOST]
    rfid = config[DOMAIN]['rfid']
    refresh_interval = config[DOMAIN]['refresh_interval']

    keba = KebaHandler(hass, host, rfid, refresh_interval)
    hass.data[DOMAIN] = keba

    # Register services to hass
    async def async_execute_service(call):
        """Execute a service to KEBA charging station.

        This must be a member function as we need access to the hass
        object here.
        """
        function_name = _SERVICE_MAP[call.service]
        function_call = getattr(keba, function_name)
        hass.async_create_task(function_call(call.data))

    # Set failsafe mode at start up of home assistant
    failsafe = config[DOMAIN]['failsafe']
    timeout = config[DOMAIN]['failsafe_timeout'] if failsafe else 0
    fallback = config[DOMAIN]['failsafe_fallback'] if failsafe else 0
    persist = config[DOMAIN]['failsafe_persist'] if failsafe else 0
    try:
        hass.loop.create_task(keba.set_failsafe(timeout, fallback, persist))
    except ValueError as e:
        _LOGGER.warning("Could not set failsafe mode %s", e)

    # Register services
    for service in _SERVICE_MAP:
        hass.services.async_register(DOMAIN, service, async_execute_service)

    for domain in SUPPORTED_COMPONENTS:
        hass.async_create_task(
            discovery.async_load_platform(hass, domain, DOMAIN, {}, config))

    return True


class KebaHandler(KebaKeContact):
    """Representation of a KEBA charging station connection."""

    def __init__(self, hass, host, rfid, refresh_interval):
        """Constructor."""
        super().__init__(host)

        self._update_listeners = []
        self._hass = hass
        self.rfid = rfid

        # Ensure at least 5 seconds delay
        self._refresh_interval = max(5, refresh_interval)
        hass.loop.create_task(self.periodic())

    async def periodic(self):
        """Send update requests asyncio style."""
        while True:
            await asyncio.sleep(self._refresh_interval)
            self._hass.async_create_task(self.request_data())

    def callback(self, data):
        """Handle component notification via callback."""
        super().callback(data)

        # Inform entities about updated values
        for listener in self._update_listeners:
            listener()

        _LOGGER.debug("Updated data: %s, notifying %d listeners",
                      self.data, len(self._update_listeners))

    async def async_set_energy(self, param):
        """Set energy target in async way."""
        try:
            energy = param['energy']
            self._hass.loop.create_task(self.set_energy(energy))
        except (KeyError, ValueError) as e:
            _LOGGER.warning("Energy value is not correct %s", e)

    async def async_set_current(self, param):
        """Set current maximum in async way."""
        try:
            current = param['current']
            self._hass.loop.create_task(self.set_current(current))
        except (KeyError, ValueError) as e:
            _LOGGER.warning("Energy value is not correct %s", e)

    async def async_start(self, param=None):
        """Authorize EV in async way."""
        self._hass.loop.create_task(self.start(self.rfid))

    async def async_stop(self, param=None):
        """De-authorize EV in async way."""
        self._hass.loop.create_task(self.stop(self.rfid))

    async def async_ena1(self, param=None):
        """Enable EV in async way."""
        self._hass.loop.create_task(self.enable(1))

    async def async_ena0(self, param=None):
        """Disable EV in async way."""
        self._hass.loop.create_task(self.enable(0))

    async def async_set_failsafe(self, param=None):
        """Set failsafe mode in async way."""
        try:
            timout = param['failsafe_timeout']
            fallback = param['failsafe_fallback']
            persist = param['failsafe_persist']
            self._hass.loop.create_task(
                self.set_failsafe(timout, fallback, persist)
            )
        except (KeyError, ValueError) as e:
            _LOGGER.warning("Energy value is not correct %s", e)

    def add_update_listener(self, listener):
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)
