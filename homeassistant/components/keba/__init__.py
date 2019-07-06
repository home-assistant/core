"""Support for KEBA charging stations."""
import asyncio
import json
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'keba'
SUPPORTED_COMPONENTS = ['binary_sensor', 'sensor', "lock"]

SERVICE_UPDATE_STATE = 'update_state'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional('rfid', default='00845500'): cv.string,
        vol.Optional('failsafe', default=False): cv.boolean,
        vol.Optional('failsafe_timeout', default=30): cv.positive_int,
        vol.Optional('failsafe_fallback', default=6): cv.positive_int,
        vol.Optional('failsafe_save', default=0): cv.positive_int,
        vol.Optional('refresh_interval', default=5): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)

_SERVICE_MAP = {
    'authorize ': 'async_authorize',
    'deauthorize ': 'async_deauthorize',
    'set_energy ': 'async_set_energy',
    'set_curr': 'async_set_max_current',
    'start': 'async_start',
    'stop': 'async_stop'
}


async def async_setup(hass, config):
    """Check connecitivty and version of KEBA charging station."""
    # Setup KebaProtocol as communication handler
    host = config[DOMAIN][CONF_HOST]
    rfid = config[DOMAIN]['rfid']
    refresh_interval = config[DOMAIN]['refresh_interval']

    keba = KebaProtocol(hass, rfid, refresh_interval)
    hass.data[DOMAIN] = keba

    await hass.loop.create_datagram_endpoint(lambda: keba,
                                             local_addr=('0.0.0.0', 7090),
                                             remote_addr=(host, 7090))

    # Register services to hass
    async def async_execute_service(call):
        """Execute a service to KEBA charging station.

        This must be a member function as we need access to the keba
        object here.
        """
        keba = hass.data[DOMAIN]
        function_name = _SERVICE_MAP[call.service]
        function_call = getattr(keba, function_name)

        if 'set_max_current' in function_name:
            if 'current' in call.data:
                current = float(call.data['current'])
                if isinstance(current, (int, float)):
                    hass.async_create_task(function_call(current))
                else:
                    _LOGGER.warning("Current is not of type int or float")
            else:
                _LOGGER.warning("Current value not given in service call")
        elif 'set_energy' in function_name:
            if 'energy' in call.data:
                energy = call.data['energy']
                if isinstance(energy, (int, float)):
                    hass.async_create_task(function_call(energy))
                else:
                    _LOGGER.warning("Energy is not of type int or float")
            else:
                _LOGGER.warning("Energy value not given in service call")
        else:
            hass.async_create_task(function_call())

    # activate failsafe mode if enabled
    if config[DOMAIN]['failsafe']:
        failsafe_timeout = config[DOMAIN]['failsafe_timeout']
        if failsafe_timeout < 10 or failsafe_timeout > 600:
            _LOGGER.warning("Failsafe timeout not allowed, setting to 30 "
                            "seconds.")
            failsafe_timeout = 30

        failsafe_fallback = config[DOMAIN]['failsafe_fallback']
        if (failsafe_fallback < 6 and failsafe_fallback != 0) \
           or failsafe_fallback > 63:
            _LOGGER.warning("Failsafe fallbock current not allowed, setting "
                            "to 6 A")
            failsafe_fallback = 6

        failsafe_save = config[DOMAIN]['failsafe_save']
        if failsafe_save not in [0, 1]:
            _LOGGER.warning("Failsafe save not allowed, setting to 0")
            failsafe_save = 0

        keba.send('failsafe ' + str(failsafe_timeout) + ' '
                  + str(failsafe_fallback * 1000) + ' ' + str(failsafe_save))
    else:
        keba.send('failsafe 0 0 0')

    # Register services
    for service in _SERVICE_MAP:
        hass.services.async_register(DOMAIN, service, async_execute_service)

    for domain in SUPPORTED_COMPONENTS:
        hass.async_create_task(
            discovery.async_load_platform(hass, domain, DOMAIN, {}, config))

    return True


class KebaProtocol(asyncio.DatagramProtocol):
    """Representation of a KEBA charging station connection."""

    data = {}
    rfid = ""

    def __init__(self, hass, rfid, refresh_interval):
        """Constructor."""
        super().__init__()
        self._update_listeners = []
        self._transport = None
        self._hass = hass
        self.rfid = rfid
        self._refresh_interval = refresh_interval

        hass.loop.create_task(self.periodic())

    async def periodic(self):
        """Send update requests asyncio style."""
        while True:
            await asyncio.sleep(self._refresh_interval)

            if self._transport is not None:
                self._hass.async_create_task(self.async_request_reports())
            else:
                _LOGGER.warning("Update is not possible due to "
                                "connection issues")

    def connection_made(self, transport):
        """Start regular update process after initial connection created."""
        _LOGGER.debug("UDP connection setup complete. Update values.")
        self._transport = transport
        self._hass.async_create_task(self.async_request_reports())

    def error_received(self, exc):
        """Log error after receiving."""
        _LOGGER.error("Error received: %s", exc)

    def connection_lost(self, exc):
        """Set state offline if connection is lost."""
        _LOGGER.error("Connection lost.")
        self.data['Online'] = False

    def datagram_received(self, data, addr):
        """Handle received datagrams."""
        decoded_data = data.decode()

        if 'TCH-OK :done' in decoded_data:
            _LOGGER.debug("Command accepted: %s", decoded_data)
            return True

        if 'TCH-ERROR' in decoded_data:
            _LOGGER.warning("Command rejected: %s", decoded_data)
            return False

        json_rcv = json.loads(data.decode())

        # Prepare received data
        if 'ID' in json_rcv:
            if json_rcv['ID'] == '1':
                try:
                    # Extract product version
                    product_string = json_rcv['Product']
                    if "P30" in product_string:
                        json_rcv['Product'] = "KEBA P30"
                    elif "P20" in product_string:
                        json_rcv['Product'] = "KEBA P20"
                    elif "BMW" in product_string:
                        json_rcv['Product'] = "BMW Wallbox"
                except KeyError:
                    _LOGGER.warning("Could not extract report 1 data for KEBA "
                                    "charging station")
            elif json_rcv['ID'] == '2':
                try:
                    json_rcv['Max curr'] = json_rcv['Max curr'] / 1000.0
                    json_rcv['Curr HW'] = json_rcv['Curr HW'] / 1000.0
                    json_rcv['Curr user'] = json_rcv['Curr user'] / 1000.0
                    json_rcv['Curr FS'] = json_rcv['Curr FS'] / 1000.0
                    json_rcv['Curr timer'] = json_rcv['Curr timer'] / 1000.0
                    json_rcv['Setenergy'] = round(
                        json_rcv['Setenergy'] / 10000.0, 2)
                except KeyError:
                    _LOGGER.warning("Could not extract report 2 data for KEBA "
                                    "charging station")
            elif json_rcv['ID'] == '3':
                try:
                    json_rcv['I1'] = json_rcv['I1'] / 1000.0
                    json_rcv['I2'] = json_rcv['I2'] / 1000.0
                    json_rcv['I3'] = json_rcv['I3'] / 1000.0
                    json_rcv['P'] = round(json_rcv['P'] / 1000000.0, 2)
                    json_rcv['PF'] = json_rcv['PF'] / 1000.0
                    json_rcv['E pres'] = round(json_rcv['E pres'] / 10000.0, 2)
                    json_rcv['E total'] = int(json_rcv['E total'] / 10000)
                except KeyError:
                    _LOGGER.warning("Could not extract report 3 data for KEBA "
                                    "charging station")
        else:
            _LOGGER.warning("Unkown response from Keba charging station")
            return False

        # Join data to internal data store
        self.data.update(json_rcv)
        self.data['Online'] = True

        # Inform enteties about updated values
        for listener in self._update_listeners:
            listener()

        _LOGGER.debug("Updated data: %s, notifying %d listeners",
                      self.data, len(self._update_listeners))

    def send(self, payload):
        """Check connection to KEBA charging station."""
        _LOGGER.debug("Send %s", payload)
        self._transport.sendto(payload.encode())

    async def async_authorize(self, *_):
        """Authorize a charging process with predefined RFID tag."""
        _LOGGER.debug("Authorize charging rfid: %s", self.rfid)
        self.send("start " + self.rfid)

    async def async_deauthorize(self, *_):
        """Deauthorize a charging process with predefined RFID tag."""
        _LOGGER.debug("Deauthorize charging rfid: %s", self.rfid)
        self.send("stop " + self.rfid)

    async def async_start(self, *_):
        """Start a charging process."""
        _LOGGER.debug("ena 1")
        self.send("ena 1")

    async def async_stop(self, *_):
        """Stop a charging process."""
        _LOGGER.debug("ena 0")
        self.send("ena 0")

    async def async_set_energy(self, energy, *_):
        """Set energy target."""
        _LOGGER.debug("Set_max_current to %s kWh", str(energy))
        self.send("setenergy " + str(int(energy * 10000)))

    async def async_set_max_current(self, current, *_):
        """Check connection to KEBA charging station."""
        if current < 6:
            _LOGGER.debug("current is below 6 A (%s), setting to 6 A",
                          str(current))
            self.send("curr " + str(6000))
        if current > 63:
            _LOGGER.debug("current is above 63 A (%s), setting to 63 A",
                          str(current))
            self.send("curr " + str(63000))
        else:
            _LOGGER.debug("Set_max_current to %s A", str(current))
            self.send("curr " + str(current * 1000))

    async def async_request_reports(self, *_):
        """Update the state of the Keba charging station.

        Notify all listeners about the update.
        """
        self.send("report 1")
        await asyncio.sleep(0.2)
        self.send("report 2")
        await asyncio.sleep(0.2)
        self.send("report 3")
        await asyncio.sleep(0.2)

    def get_value(self, key):
        """Return wallbox value for given key if available, otherwise None."""
        if self.data is None:
            return None
        try:
            value = self.data[key]
            return value
        except KeyError:
            return None

        return None

    def add_update_listener(self, listener):
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)
