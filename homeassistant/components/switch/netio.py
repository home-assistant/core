"""
homeassistant.components.switch.netio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure a NETIO switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.netio/
"""
import logging
from homeassistant.const import *
from homeassistant.helpers import validate_config
from homeassistant.components.netio import DOMAIN, DEVICES
from homeassistant.components.switch import SwitchDevice, \
    ATTR_CURRENT_POWER_MWH

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = [DOMAIN]


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Configure the netio linl """

    if validate_config({DOMAIN: config}, {DOMAIN: [CONF_PORTS,
                       CONF_HOST]}, _LOGGER):
        for key in config[CONF_PORTS]:
            switch = NetioSwitch(config[CONF_HOST], key,
                                 config[CONF_PORTS][key])
            add_devices_callback([switch])
            DEVICES[config[CONF_HOST]].entities.append(switch)


class NetioSwitch(SwitchDevice):
    """ Provide a netio linked switch"""
    def __init__(self, host, port, name):
        self._name = name
        self.port = port
        self.netio = DEVICES[host].netio

    @property
    def name(self):
        return self._name

    def turn_on(self):
        self._set(True)

    def turn_off(self):
        self._set(False)

    def _set(self, value):
        val = list('uuuu')
        val[self.port-1] = "1" if value else "0"
        self.netio.get('port list %s' % ''.join(val))

    @property
    def is_on(self):
        return self.netio.states[self.port-1]

    # @property
    # def state(self):
    #     return STATE_ON if self.is_on else STATE_OFF

    def update(self):
        self.netio.update()

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        return {ATTR_CURRENT_POWER_MWH: self.current_power_mhw}

    @property
    def current_power_mhw(self):
        return self.netio.consumptions[self.port-1]
