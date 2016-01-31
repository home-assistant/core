"""
homeassistant.components.switch.netio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The Netio platform allows you to control your [Netio]
(http://www.netio-products.com/en/overview/) Netio4, Netio4 All and Netio 230B.
These are smart outlets controllable through ethernet and/or WiFi that reports
consumptions (Netio4all).

To use these devices in your installation, add the following to your
configuration.yaml file:
```
switch:
  - platform: netio
    host: netio-living
    outlets:
      1: "AppleTV"
      2: "Htpc"
      3: "Lampe Gauche"
      4: "Lampe Droite"
  - platform: netio
    host: 192.168.1.43
    port: 1234
    username: user
    password: pwd
    outlets:
      1: "Nothing..."
      4: "Lampe du fer"
```

To get pushed updates from the netio devices, one can add this lua code in the
device interface as an action triggered on "Netio" "System variables updated"
with an 'Always' schedule:

``
-- this will send socket and consumption status updates via CGI
-- to given address. Associate with 'System variables update' event
-- to get consumption updates when they show up

local address='ha:8123'
local path = '/api/netio'


local output = {}
for i = 1, 4 do for _, what in pairs({'state', 'consumption',
                        'cumulatedConsumption', 'consumptionStart'}) do
    local varname = string.format('output%d_%s', i, what)
    table.insert(output,
        varname..'='..tostring(devices.system[varname]):gsub(" ","|"))
end end

local qs = table.concat(output, '&')
local url = string.format('http://%s%s?%s', address, path, qs)
devices.system.CustomCGI{url=url}
```


For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.netio/

"""
import logging
import socket
# from homeassistant import util
from datetime import timedelta
from collections import namedtuple
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, \
    CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP, STATE_ON
from homeassistant.helpers import validate_config
from homeassistant.components.switch import SwitchDevice, \
    ATTR_CURRENT_POWER_W, ATTR_TOTAL_CONSUMPTION_KWH

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']
REQUIREMENTS = ['pynetio>=0.1.5.2']
DEFAULT_USERNAME = 'admin'
DEFAULT_PORT = 1234
CONF_OUTLETS = "outlets"
REQ_CONF = [CONF_HOST, CONF_OUTLETS]
URL_API_NETIO_EP = "/api/netio"

device = namedtuple('device', ['netio', 'entities'])
DEVICES = {}
ATTR_START_DATE = 'start_date'
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Configure the netio linl """
    from pynetio import Netio

    if validate_config({"conf": config}, {"conf": [CONF_OUTLETS,
                                                   CONF_HOST]}, _LOGGER):
        try:
            dev = Netio(config[CONF_HOST],
                        config.get(CONF_PORT, DEFAULT_PORT),
                        config.get(CONF_USERNAME, DEFAULT_USERNAME),
                        config.get(CONF_PASSWORD, DEFAULT_USERNAME))
            DEVICES[config[CONF_HOST]] = device(dev, [])
        except:
            _LOGGER.error('Cannot connect to %s' % config[CONF_HOST])
            return False

        for key in config[CONF_OUTLETS]:
            switch = NetioSwitch(DEVICES[config[CONF_HOST]].netio, key,
                                 config[CONF_OUTLETS][key])
            DEVICES[config[CONF_HOST]].entities.append(switch)

        add_devices_callback(DEVICES[config[CONF_HOST]].entities)

    hass.http.register_path('GET', URL_API_NETIO_EP, _got_push)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, dispose)
    return True


def _got_push(handler, path_match, data):
    """ To handle updates from http GET """

    host = socket.gethostbyaddr(handler.client_address[0])[0].split('.')[0]
    states, consumptions, cumulatedConsumptions, startDates = [], [], [], []

    for i in range(1, 5):
        out = 'output_%d' % i
        states.append(data.get('%s_state' % out) == STATE_ON)
        consumptions.append(float(data.get('%s_consumption' % out, 0)))
        cumulatedConsumptions.append(
            float(data.get('%s_cumulatedConsumption' % out, 0)) / 1000)
        startDates.append(data.get('%s_consumptionStart' % out, ""))

    _LOGGER.debug('%s: %s, %s, %s since %s' % (
                  host, states, consumptions,
                  cumulatedConsumptions, startDates))

    DEVICES[host].netio.consumptions = consumptions
    DEVICES[host].netio.cumulatedConsumptions = cumulatedConsumptions
    DEVICES[host].netio.states = states
    DEVICES[host].netio.startDates = startDates

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
        # if self.netio.update.__name__ != 'wrapper':
        #     self.netio.update = util.Throttle(MIN_TIME_BETWEEN_SCANS)(
        #           self.netio.update)

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
