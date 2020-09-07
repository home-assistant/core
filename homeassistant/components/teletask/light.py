"""Support for Teletask/IP lights."""
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    Light,
)
from homeassistant.components.teletask import DATA_TELETASK
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = "address"
CONF_DOIP_COMP = "doip_component"
CONF_BRIGHTNESS_ADDRESS = "brightness_address"

DEFAULT_NAME = "Teletask Light"
DEPENDENCIES = ["teletask"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_BRIGHTNESS_ADDRESS, default=""): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DOIP_COMP, default="relay"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info):
    """Set up lights for Teletask platform."""
    await async_add_entities_config(hass, config, async_add_entities)


@callback
async def async_add_entities_config(hass, config, async_add_entities):
    """Set up light for Teletask platform configured within platform."""
    import teletask

    light = teletask.devices.Light(
        teletask=hass.data[DATA_TELETASK].teletask,
        name=config.get(CONF_NAME),
        group_address_switch=config.get(CONF_ADDRESS),
        group_address_brightness=config.get(CONF_BRIGHTNESS_ADDRESS),
        doip_component=config.get(CONF_DOIP_COMP),
    )
    await light.current_state()
    hass.data[DATA_TELETASK].teletask.devices.add(light)
    async_add_entities([TeletaskLight(light)])


class TeletaskLight(Light):
    """Representation of a Teletask light."""

    def __init__(self, device):
        """Initialize of Teletask light."""
        self.device = device
        self.teletask = device.teletask

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            await self.async_update_ha_state()

        self.device.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

    @property
    def name(self):
        """Return the name of the Teletask device."""
        return self.device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.hass.data[DATA_TELETASK].connected

    @property
    def brightness(self):
        """Return the brightness of this light between 0..100."""
        return (
            self.device.current_brightness if self.device.supports_brightness else None
        )

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device.state

    @property
    def supported_features(self):
        """Flag supported features."""
        flags = 0
        if self.device.supports_brightness:
            flags |= SUPPORT_BRIGHTNESS
        return flags

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            if self.device.supports_brightness:
                await self.device.set_brightness(int(kwargs[ATTR_BRIGHTNESS]))
        else:
            await self.device.set_on()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.device.set_off()
