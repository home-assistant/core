"""
homeassistant.components.netio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface Koukaam Netio Switches.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/netio/
"""

import logging
import socket
from pynetio import Netio
from collections import namedtuple
from homeassistant.const import *
from homeassistant.helpers import validate_config

DEPENDENCIES = ['http']
REQUIREMENTS = ['pynetio>=0.1.3']
DOMAIN = __name__.split('.')[-1]
DEFAULT_USERNAME = 'admin'
DEFAULT_PORT = 1234
REQ_CONF = [CONF_HOST, CONF_NAME]

_LOGGER = logging.getLogger(__name__)
DEVICES = {}
CONFIG = {}

URL_API_NETIO_EP = "/api/netio"

device = namedtuple('device', ['netio', 'entities'])


def setup(hass, config):
    "Set up the different netio devices"
    for item in config[DOMAIN]:
        if validate_config({DOMAIN: item}, {DOMAIN: REQ_CONF}, _LOGGER):
            try:
                dev = Netio(item[CONF_HOST],
                            item.get(CONF_PORT, DEFAULT_PORT),
                            item.get(CONF_USERNAME, DEFAULT_USERNAME),
                            item.get(CONF_PASSWORD, DEFAULT_USERNAME))
                DEVICES[item[CONF_HOST]] = DEVICES[item[CONF_NAME]] = \
                    device(dev, [])
            except:
                _LOGGER.error('Cannot connect to %s' % item)

    hass.http.register_path('GET', URL_API_NETIO_EP, _got_push)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, dispose)
    return True


def _got_push(handler, path_match, data):
    """ To handle updates from http GET """

    name = socket.gethostbyaddr(handler.client_address[0])[0].split('.')[0]
    states, consumptions = [], []
    for i in range(1, 5):
        states.append(
            True if data.get('output%d_state' % i) == 'on' else False)
        consumptions.append(float(data.get('output%d_consumption' % i)))
    _LOGGER.debug('%s: %s, %s' %
                  (name, states, consumptions))
    DEVICES[name].netio._consumptions = consumptions
    DEVICES[name].netio._states = states
    [x.update_ha_state() for x in DEVICES[name].entities]


def dispose(event):
    "Close connections to Netio Devices"
    [value.netio.stop() for key, value in DEVICES.items()]
