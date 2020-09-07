"""Support for Teletask/IP switches."""
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.components.teletask import DATA_TELETASK
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

CONF_ADDRESS = "address"
CONF_DOIP_COMP = "doip_component"

DEFAULT_NAME = "Teletask Switch"
DEPENDENCIES = ["teletask"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DOIP_COMP, default="relay"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info):
    """Set up switches for Teletask platform."""
    await async_add_entities_config(hass, config, async_add_entities)


@callback
async def async_add_entities_config(hass, config, async_add_entities):
    """Set up switch for Teletask platform configured within platform."""
    import teletask

    switch = teletask.devices.Switch(
        hass.data[DATA_TELETASK].teletask,
        name=config.get(CONF_NAME),
        group_address_switch=config.get(CONF_ADDRESS),
        doip_component=config.get(CONF_DOIP_COMP),
    )
    await switch.current_state()
    hass.data[DATA_TELETASK].teletask.devices.add(switch)
    async_add_entities([TeletaskSwitch(switch)])


class TeletaskSwitch(SwitchDevice):
    """Representation of a Teletask switch."""

    def __init__(self, device):
        """Initialize of Teletask switch."""
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
    def is_on(self):
        """Return true if switch is on."""
        return self.device.state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.device.set_on()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.device.set_off()
