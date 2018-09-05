"""
Support for KNX/IP fans.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.knx/
"""
import logging
import voluptuous as vol

from homeassistant.components.knx import DATA_KNX, ATTR_DISCOVER_DEVICES
from homeassistant.components.fan import PLATFORM_SCHEMA, FanEntity, SUPPORT_SET_SPEED, ATTR_SPEED
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = 'speed_address'
CONF_STATE_ADDRESS = 'speed_state_address'

DEFAULT_NAME = 'KNX Fan'
DEPENDENCIES = ['knx']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_ADDRESS): cv.string,
})


async def async_setup_platform(hass, config, async_add_devices,
                         discovery_info=None):
    """Set up fan(s) for KNX platform."""
    if discovery_info is not None:
        async_add_devices_discovery(hass, discovery_info, async_add_devices)
    else:
        async_add_devices_config(hass, config, async_add_devices)


@callback
def async_add_devices_discovery(hass, discovery_info, async_add_devices):
    """Set up fans for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXFan(hass, device))
    async_add_devices(entities)


@callback
def async_add_devices_config(hass, config, async_add_devices):
    """Set up fan for KNX platform configured within plattform."""
    import xknx
    fan = xknx.devices.Fan(
        hass.data[DATA_KNX].xknx,
        name=config.get(CONF_NAME),
        group_address_speed=config.get(CONF_ADDRESS),
        group_address_speed_state=config.get(CONF_STATE_ADDRESS))
    hass.data[DATA_KNX].xknx.devices.add(fan)
    async_add_devices([KNXFan(hass, fan)])


class KNXFan(FanEntity):
    """Representation of a KNX fan."""

    def __init__(self, hass, device):
        """Initialize the entity."""
        self.device = device
        self.hass = hass
        self.async_register_callbacks()

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""
        async def after_update_callback(device):
            """Callback after device was updated."""
            # pylint: disable=unused-argument
            await self.async_update_ha_state()
        self.device.register_device_updated_cb(after_update_callback)

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.device.current_speed() != 0

    @property
    def should_poll(self):
        """No polling needed within KNX."""
        return False

    @property
    def speed(self) -> str:
        """Return the current speed."""
        if self.device.current_speed() is not None:
            return self.device.current_speed()
        else:
            return 0

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [0, 25, 50, 75, 100]

    async def async_turn_on(self, **kwargs):
        """Turn on the entity."""
        if ATTR_SPEED in kwargs:
            speed = int(kwargs[ATTR_SPEED])
        else:
            speed = 50
        await self._internal_set_speed(speed)

    async def async_turn_off(self, **kwargs):
        """Turn off the entity."""
        self.oscillate(False)
        await self._internal_set_speed(0)

    async def async_set_speed(self, **kwargs):
        """Set the speed of the fan."""
        await self._internal_set_speed(int(kwargs[ATTR_SPEED]))

    async def _internal_set_speed(self, speed: int):
        await self.device.set_speed(speed)

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""

    def oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""

    @property
    def current_direction(self) -> str:
        """Fan direction."""
        return None

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED
