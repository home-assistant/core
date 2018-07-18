"""
Support for KNX/IP switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.knx/
"""

import voluptuous as vol

from homeassistant.components.knx import ATTR_DISCOVER_DEVICES, DATA_KNX
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
CONF_STATE_ADDRESS = 'state_address'

DEFAULT_NAME = 'KNX Switch'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_ADDRESS): cv.string,
})


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up switch(es) for KNX platform."""
    if discovery_info is not None:
        async_add_devices_discovery(hass, discovery_info, async_add_devices)
    else:
        async_add_devices_config(hass, config, async_add_devices)


@callback
def async_add_devices_discovery(hass, discovery_info, async_add_devices):
    """Set up switches for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXSwitch(hass, device))
    async_add_devices(entities)


@callback
def async_add_devices_config(hass, config, async_add_devices):
    """Set up switch for KNX platform configured within platform."""
    import xknx
    switch = xknx.devices.Switch(
        hass.data[DATA_KNX].xknx,
        name=config.get(CONF_NAME),
        group_address=config.get(CONF_ADDRESS),
        group_address_state=config.get(CONF_STATE_ADDRESS))
    hass.data[DATA_KNX].xknx.devices.add(switch)
    async_add_devices([KNXSwitch(hass, switch)])


class KNXSwitch(SwitchDevice):
    """Representation of a KNX switch."""

    def __init__(self, hass, device):
        """Initialize of KNX switch."""
        self.device = device
        self.hass = hass
        self.async_register_callbacks()

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""
        async def after_update_callback(device):
            """Call after device was updated."""
            await self.async_update_ha_state()
        self.device.register_device_updated_cb(after_update_callback)

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def available(self):
        """Return true if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self):
        """Return the polling state. Not needed within KNX."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.device.state

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.device.set_on()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.device.set_off()
