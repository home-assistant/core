"""
Support for KNX/IP switches via XKNX.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.xknx/
"""
import asyncio
import voluptuous as vol

from homeassistant.components.xknx import DATA_XKNX, ATTR_DISCOVER_DEVICES
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'address'
CONF_STATE_ADDRESS = 'state_address'

DEFAULT_NAME = 'XKNX Switch'
DEPENDENCIES = ['xknx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_ADDRESS): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, add_devices,
                         discovery_info=None):
    """Set up switch(es) for XKNX platform."""
    if DATA_XKNX not in hass.data \
            or not hass.data[DATA_XKNX].initialized:
        return False

    if discovery_info is not None:
        add_devices_from_component(hass, discovery_info, add_devices)
    else:
        add_devices_from_platform(hass, config, add_devices)

    return True


def add_devices_from_component(hass, discovery_info, add_devices):
    """Set up switches for XKNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_XKNX].xknx.devices[device_name]
        entities.append(XKNXSwitch(hass, device))
    add_devices(entities)


def add_devices_from_platform(hass, config, add_devices):
    """Set up switch for XKNX platform configured within plattform."""
    import xknx
    switch = xknx.devices.Switch(
        hass.data[DATA_XKNX].xknx,
        name=config.get(CONF_NAME),
        group_address=config.get(CONF_ADDRESS),
        group_address_state=config.get(CONF_STATE_ADDRESS))
    hass.data[DATA_XKNX].xknx.devices.add(switch)
    add_devices([XKNXSwitch(hass, switch)])


class XKNXSwitch(SwitchDevice):
    """Representation of a XKNX switch."""

    def __init__(self, hass, device):
        """Initialization of XKNXSwitch."""
        self.device = device
        self.hass = hass
        self.register_callbacks()

    def register_callbacks(self):
        """Register callbacks to update hass after device was changed."""
        @asyncio.coroutine
        def after_update_callback(device):
            """Callback after device was updated."""
            # pylint: disable=unused-argument
            yield from self.async_update_ha_state()
        self.device.register_device_updated_cb(after_update_callback)

    @property
    def name(self):
        """Return the name of the XKNX device."""
        return self.device.name

    @property
    def should_poll(self):
        """No polling needed within XKNX."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.device.state

    @asyncio.coroutine
    def async_turn_on(self):
        """Turn the device on."""
        yield from self.device.set_on()

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn the device off."""
        yield from self.device.set_off()
