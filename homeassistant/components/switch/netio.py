"""
homeassistant.components.switch.netio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a NETIO switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.netio/
"""
import logging
import socket
from pynetio import Netio
from collections import namedtuple
from homeassistant.const import *
from homeassistant.helpers import validate_config
from homeassistant.components.switch import SwitchDevice, \
    ATTR_CURRENT_POWER_W, ATTR_TOTAL_CONSUMPTION_KWH

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']
REQUIREMENTS = ['pynetio>=0.1.5.1']
DEFAULT_USERNAME = 'admin'
DEFAULT_PORT = 1234
REQ_CONF = [CONF_HOST, CONF_PORTS]
URL_API_NETIO_EP = "/api/netio"

device = namedtuple('device', ['netio', 'entities'])
DEVICES = {}


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Configure the netio linl """

    if validate_config({"conf": config}, {"conf": [CONF_PORTS,
                                                   CONF_HOST]}, _LOGGER):
        if not config[CONF_HOST] in DEVICES:
            try:
                dev = Netio(config[CONF_HOST],
                            config.get(CONF_PORT, DEFAULT_PORT),
                            config.get(CONF_USERNAME, DEFAULT_USERNAME),
                            config.get(CONF_PASSWORD, DEFAULT_USERNAME))
                DEVICES[config[CONF_HOST]] = device(dev, [])
            except:
                _LOGGER.error('Cannot connect to %s' % config[CONF_HOST])

        if DEVICES.get(config[CONF_HOST]):
            for key in config[CONF_PORTS]:
                switch = NetioSwitch(DEVICES[config[CONF_HOST]].netio, key,
                                     config[CONF_PORTS][key])
                add_devices_callback([switch])
                DEVICES[config[CONF_HOST]].entities.append(switch)

    hass.http.register_path('GET', URL_API_NETIO_EP, _got_push)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, dispose)
    return True


def _got_push(handler, path_match, data):
    """ To handle updates from http GET """

    host = socket.gethostbyaddr(handler.client_address[0])[0].split('.')[0]
    states, consumptions, cumulatedConsumptions, startDates = [], [], [], []

    for i in range(1, 5):
        states.append(
            True if data.get('output%d_state' % i) == STATE_ON else False)
        consumptions.append(float(data.get('output%d_consumption' % i, 0)))
        cumulatedConsumptions.append(
            float(data.get('output%d_cumulatedConsumption' % i, 0)) / 1000)
        startDates.append(data.get('output%d_consumptionStart' % i, ""))

    _LOGGER.debug('%s: %s, %s, %s since %s' %
            (host, states, consumptions, cumulatedConsumptions, startDates))

    DEVICES[host].netio._consumptions = consumptions
    DEVICES[host].netio._cumulatedConsumptions = cumulatedConsumptions
    DEVICES[host].netio._states = states
    DEVICES[host].netio._startDates = startDates

    [x.update_ha_state() for x in DEVICES[host].entities]


def dispose(event):
    "Close connections to Netio Devices"
    [value.netio.stop() for key, value in DEVICES.items()]


class NetioSwitch(SwitchDevice):
    """ Provide a netio linked switch"""

    def __init__(self, netio, port, name):
        self._name = name
        self.port = port
        self.netio = netio

    @property
    def name(self):
        return self._name

    def turn_on(self):
        self._set(True)

    def turn_off(self):
        self._set(False)

    def _set(self, value):
        val = list('uuuu')
        val[self.port - 1] = "1" if value else "0"
        self.netio.get('port list %s' % ''.join(val))

    @property
    def is_on(self):
        return self.netio.states[self.port - 1]

    # @property
    # def state(self):
    #     return STATE_ON if self.is_on else STATE_OFF

    def update(self):
        self.netio.update()

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        return {ATTR_CURRENT_POWER_W: self.current_power_w,
                ATTR_TOTAL_CONSUMPTION_KWH: self.cumulated_consumption_kwh,
                ATTR_START_DATE: self.start_dates.split('|')[0]}

    @property
    def current_power_w(self):
        return self.netio.consumptions[self.port - 1]

    @property
    def cumulated_consumption_kwh(self):
        return self.netio.cumulatedConsumptions[self.port - 1]

    @property
    def start_dates(self):
        return self.netio.startDates[self.port - 1]

