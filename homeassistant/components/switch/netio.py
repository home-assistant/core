"""
The Netio switch component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.netio/
"""
import logging
import requests
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP, STATE_ON)
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['requests>=2.1.4']
DEPENDENCIES = ['http']

ATTR_CURRENT_POWER_MWH = 'current_power_mwh'
ATTR_CURRENT_POWER_W = 'current_power_w'
ATTR_START_DATE = 'start_date'
ATTR_TODAY_MWH = 'today_mwh'
ATTR_TOTAL_CONSUMPTION_KWH = 'total_energy_kwh'
CONF_OUTLETS = 'outlets'

DEVICES = {}

URL_API_NETIO_EP = '/api/netio/{host}'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_OUTLETS): {int: cv.string},
})

logger = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Configure the Netio platform."""    

    if len(DEVICES) == 0:
        hass.http.register_view(NetioApiView)

    host = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)
    DEVICES[host] = {}

    for key in config[CONF_OUTLETS]:
        switch = NetioSwitch(host, password, config[CONF_OUTLETS][key], key)            
        DEVICES[host][key]=switch

    add_devices(list(DEVICES[host].values()))

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, dispose)
    return True


def dispose(event):
    """Clean up whatever needs to be"""


class NetioApiView(HomeAssistantView):
    """WSGI handler class."""

    url = URL_API_NETIO_EP
    name = 'api:netio'

    @callback
    def get(self, request, host):
        """Request handler."""
        hass = request.app['hass']
        data = request.GET

        for outlet, switch in DEVICES[host].items():
            out = 'output%d' % outlet
            switch._state = data.get('%s_state' % out) == STATE_ON
            switch.current_power_w = float(data.get('%s_consumption' % out, 0))
            switch.cumulated_consumption_kwh =\
                float(data.get('%s_cumulatedConsumption' % out, 0)) / 1000
            switch.start_date = data.get('%s_consumptionStart' % out, "")
            
            hass.async_add_job(switch.async_update_ha_state())
        
        return self.json(True)


class NetioSwitch(SwitchDevice):
    """Provide a netio linked switch."""

    def __init__(self, host, password, name, outlet):
        self._name = name
        self.outlet = outlet
        self.host = host
        self.password = password

        self._state = False
        self.current_power_w = 0
        self.cumulated_consumption_kwh = 0
        self.start_date = ""

    @property
    def name(self):
        """Netio device's name."""
        return self._name

    def turn_on(self):
        """Turn switch on."""
        self._set(True)        

    def turn_off(self):
        """Turn switch off."""
        self._set(False)

    def _set(self, value):
        """Send request to Netio"""
        val = ['x'] * 4
        val[self.outlet-1] = '1' if value else '0'

        res = requests.get('http://%s/event?port=%s&pass=%s'
            %(self.host, ''.join(val), self.password))        
        
        if res.ok:
            self._state = value
            self.schedule_update_ha_state()
        else:
            logger.error (res.reason)

    @property
    def is_on(self):
        """Return switch's status."""
        return self._state

    @property
    def should_poll(self):
        """Polling needed."""
        return False

    @property
    def state_attributes(self):
        """Return optional state attributes."""
        return {
            ATTR_CURRENT_POWER_W: self.current_power_w,
            ATTR_TOTAL_CONSUMPTION_KWH: self.cumulated_consumption_kwh,         
            ATTR_START_DATE: self.start_date.split('|')[0]
        }

    @property
    def device_state_attributes(self):
        """Netio attributes"""
        return { 'host': self.host}
