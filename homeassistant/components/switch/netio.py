"""
Netio switch component.

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
local path = '/api/netio/<host>'


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
from collections import namedtuple
from datetime import timedelta
from homeassistant import util
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, \
    CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP, STATE_ON
from homeassistant.helpers import validate_config
from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']
REQUIREMENTS = ['pynetio==0.1.6']
DEFAULT_USERNAME = 'admin'
DEFAULT_PORT = 1234
URL_API_NETIO_EP = "/api/netio/<host>"

CONF_OUTLETS = "outlets"
REQ_CONF = [CONF_HOST, CONF_OUTLETS]
ATTR_TODAY_MWH = "today_mwh"
ATTR_TOTAL_CONSUMPTION_KWH = "total_energy_kwh"
ATTR_CURRENT_POWER_MWH = "current_power_mwh"
ATTR_CURRENT_POWER_W = "current_power_w"

Device = namedtuple('device', ['netio', 'entities'])
DEVICES = {}
ATTR_START_DATE = 'start_date'
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Configure the netio platform."""
    from pynetio import Netio

    if validate_config({"conf": config}, {"conf": [CONF_OUTLETS,
                                                   CONF_HOST]}, _LOGGER):
        if len(DEVICES) == 0:
            hass.wsgi.register_view(NetioApiView)

        dev = Netio(config[CONF_HOST],
                    config.get(CONF_PORT, DEFAULT_PORT),
                    config.get(CONF_USERNAME, DEFAULT_USERNAME),
                    config.get(CONF_PASSWORD, DEFAULT_USERNAME))

        DEVICES[config[CONF_HOST]] = Device(dev, [])

        # Throttle the update for all NetioSwitches of one Netio
        dev.update = util.Throttle(MIN_TIME_BETWEEN_SCANS)(dev.update)

        for key in config[CONF_OUTLETS]:
            switch = NetioSwitch(DEVICES[config[CONF_HOST]].netio, key,
                                 config[CONF_OUTLETS][key])
            DEVICES[config[CONF_HOST]].entities.append(switch)

        add_devices_callback(DEVICES[config[CONF_HOST]].entities)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, dispose)
    return True


def dispose(event):
    """Close connections to Netio Devices."""
    for _, value in DEVICES.items():
        value.netio.stop()


class NetioApiView(HomeAssistantView):
    """WSGI handler class."""

    url = URL_API_NETIO_EP
    name = "api:netio"

    def get(self, request, host):
        """Request handler."""
        data = request.args
        states, consumptions, cumulated_consumptions, start_dates = \
            [], [], [], []

        for i in range(1, 5):
            out = 'output%d' % i
            states.append(data.get('%s_state' % out) == STATE_ON)
            consumptions.append(float(data.get('%s_consumption' % out, 0)))
            cumulated_consumptions.append(
                float(data.get('%s_cumulatedConsumption' % out, 0)) / 1000)
            start_dates.append(data.get('%s_consumptionStart' % out, ""))

        _LOGGER.debug('%s: %s, %s, %s since %s', host, states,
                      consumptions, cumulated_consumptions, start_dates)

        ndev = DEVICES[host].netio
        ndev.consumptions = consumptions
        ndev.cumulated_consumptions = cumulated_consumptions
        ndev.states = states
        ndev.start_dates = start_dates

        for dev in DEVICES[host].entities:
            dev.update_ha_state()

        return self.json(True)


class NetioSwitch(SwitchDevice):
    """Provide a netio linked switch."""

    def __init__(self, netio, outlet, name):
        """Defined to handle throttle."""
        self._name = name
        self.outlet = outlet
        self.netio = netio

    @property
    def name(self):
        """Netio device's name."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return not hasattr(self, 'telnet')

    def turn_on(self):
        """Turn switch on."""
        self._set(True)

    def turn_off(self):
        """Turn switch off."""
        self._set(False)

    def _set(self, value):
        val = list('uuuu')
        val[self.outlet - 1] = "1" if value else "0"
        self.netio.get('port list %s' % ''.join(val))
        self.netio.states[self.outlet - 1] = value
        self.update_ha_state()

    @property
    def is_on(self):
        """Return switch's status."""
        return self.netio.states[self.outlet - 1]

    def update(self):
        """Called by HA."""
        self.netio.update()

    @property
    def state_attributes(self):
        """Return optional state attributes."""
        return {ATTR_CURRENT_POWER_W: self.current_power_w,
                ATTR_TOTAL_CONSUMPTION_KWH: self.cumulated_consumption_kwh,
                ATTR_START_DATE: self.start_date.split('|')[0]}

    @property
    def current_power_w(self):
        """Return actual power."""
        return self.netio.consumptions[self.outlet - 1]

    @property
    def cumulated_consumption_kwh(self):
        """Total enerygy consumption since start_date."""
        return self.netio.cumulated_consumptions[self.outlet - 1]

    @property
    def start_date(self):
        """Point in time when the energy accumulation started."""
        return self.netio.start_dates[self.outlet - 1]
