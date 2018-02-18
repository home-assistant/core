"""
Support for INSTEON PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio
import collections

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import (CONF_PORT, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ['insteonplm==0.8.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'insteon_plm'

CONF_OVERRIDE = 'device_override'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(CONF_OVERRIDE): vol.All(
            cv.ensure_list_csv, vol.Length(min=1))
        })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the connection to the PLM."""
    import insteonplm

    ipdb = IPDB()

    conf = config[DOMAIN]
    port = conf.get(CONF_PORT)
    overrides = conf.get(CONF_OVERRIDE, [])

    @callback
    def async_plm_new_device(device):
        """Detect device from transport to be delegated to platform."""

        for stateKey in device.states:
            platformInfo = ipdb[device.states[stateKey]]
            platform = platformInfo.platform
            if platform is not None:
                _LOGGER.info("New INSTEON PLM device: %s (%s) %s",
                             device.address,
                             device.states[stateKey].name,
                             platform)

                hass.async_add_job(
                    discovery.async_load_platform(
                        hass, platform, DOMAIN,
                        discovered=[{'address': device.address.hex,
                                     'stateKey': stateKey}],
                        hass_config=config))

    _LOGGER.info("Looking for PLM on %s", port)
    conn = yield from insteonplm.Connection.create(
        device=port,
        loop=hass.loop,
        workdir=hass.config.config_dir)

    plm = conn.protocol

    for device_override in overrides:
        #
        # Override the device default capabilities for a specific address
        #
        if device_override.get('cat', False):
            plm.devices.add_override(device_override['address'],
                                     'cat',
                                     device_override['cat'])
        if device_override.get('subcat', False):
            plm.devices.add_override(device_override['address'],
                                     'subcat',
                                     device_override['subcat'])
        if device_override.get('firmware', False):
            plm.devices.add_override(device_override['address'],
                                     'product_key',
                                     device_override['firmware'])
        if device_override.get('product_key', False):
            plm.devices.add_override(device_override['address'],
                                     'product_key',
                                     device_override['product_key'])

    hass.data['insteon_plm'] = plm

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, conn.close)

    plm.devices.add_device_callback(async_plm_new_device)

    return True


def common_attributes(entity, state):
    """Return the device state attributes."""
    attributes = {
        'INSTEON Address': entity.address.human,
        'Description': entity.description,
        'Model': entity.model,
        'Category': '{:02x}'.format(entity.cat),
        'Subcategory': '{:02x}'.format(entity.subcat),
        'Product Key / Firmware': '{:02x}'.format(entity.product_key),
        'Group': '{:02x}'.format(state.group)
    }
    return attributes


State = collections.namedtuple('Product', 'stateType platform')


class IPDB(object):
    """Embodies the INSTEON Product Database static data
and access methods."""

    def __init__(self):

        from insteonplm.states.onOff import (OnOffSwitch,
                                             OnOffSwitch_OutletTop,
                                             OnOffSwitch_OutletBottom,
                                             OpenClosedRelay)

        from insteonplm.states.dimmable import (DimmableSwitch,
                                                DimmableSwitch_Fan)

        from insteonplm.states.sensor import (VariableSensor,
                                              OnOffSensor,
                                              SmokeCO2Sensor,
                                              IoLincSensor)

        self.states = [State(OnOffSwitch_OutletTop, 'switch'),
                       State(OnOffSwitch_OutletBottom, 'switch'),
                       State(OpenClosedRelay, 'switch'),
                       State(OnOffSwitch, 'switch'),

                       State(IoLincSensor, 'binary_sensor'),
                       State(SmokeCO2Sensor, 'sensor'),
                       State(OnOffSensor, 'binary_sensor'),
                       State(VariableSensor, 'sensor'),

                       State(DimmableSwitch_Fan, 'fan'),
                       State(DimmableSwitch, 'light')
                      ]

    def __len__(self):
        return len(self.states)

    def __iter__(self):
        for product in self.states:
            yield product

    def __getitem__(self, key):
        for state in self.states:
            if isinstance(key, state.stateType):
                return state
        return None
