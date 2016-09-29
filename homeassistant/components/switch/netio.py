"""
The Netio switch component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.netio/
"""
import logging
from collections import namedtuple
from datetime import timedelta

import voluptuous as vol

from homeassistant import util
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP, STATE_ON)
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pynetio==0.1.6']

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_POWER_MWH = 'current_power_mwh'
ATTR_CURRENT_POWER_W = 'current_power_w'
ATTR_START_DATE = 'start_date'
ATTR_TODAY_MWH = 'today_mwh'
ATTR_TOTAL_CONSUMPTION_KWH = 'total_energy_kwh'

CONF_OUTLETS = 'outlets'

DEFAULT_PORT = 1234
DEFAULT_USERNAME = 'admin'
DEPENDENCIES = ['http']
Device = namedtuple('device', ['netio', 'entities'])
DEVICES = {}

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

REQ_CONF = [CONF_HOST, CONF_OUTLETS]

URL_API_NETIO_EP = '/api/netio/<host>'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_OUTLETS): {cv.string: cv.string},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Configure the Netio platform."""
    from pynetio import Netio

    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    port = config.get(CONF_PORT)

    if len(DEVICES) == 0:
        hass.wsgi.register_view(NetioApiView)

    dev = Netio(host, port, username, password)

    DEVICES[host] = Device(dev, [])

    # Throttle the update for all NetioSwitches of one Netio
    dev.update = util.Throttle(MIN_TIME_BETWEEN_SCANS)(dev.update)

    for key in config[CONF_OUTLETS]:
        switch = NetioSwitch(
            DEVICES[host].netio, key, config[CONF_OUTLETS][key])
        DEVICES[host].entities.append(switch)

    add_devices(DEVICES[host].entities)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, dispose)
    return True


def dispose(event):
    """Close connections to Netio Devices."""
    for _, value in DEVICES.items():
        value.netio.stop()


class NetioApiView(HomeAssistantView):
    """WSGI handler class."""

    url = URL_API_NETIO_EP
    name = 'api:netio'

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
        val[self.outlet - 1] = '1' if value else '0'
        self.netio.get('port list %s' % ''.join(val))
        self.netio.states[self.outlet - 1] = value
        self.update_ha_state()

    @property
    def is_on(self):
        """Return switch's status."""
        return self.netio.states[self.outlet - 1]

    def update(self):
        """Called by Home Assistant."""
        self.netio.update()

    @property
    def state_attributes(self):
        """Return optional state attributes."""
        return {
            ATTR_CURRENT_POWER_W: self.current_power_w,
            ATTR_TOTAL_CONSUMPTION_KWH: self.cumulated_consumption_kwh,
            ATTR_START_DATE: self.start_date.split('|')[0]
        }

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
