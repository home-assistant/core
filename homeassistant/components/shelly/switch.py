"""Switch for Shelly."""
from aioshelly import Block

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from . import ShellyDeviceWrapper
from .const import DATA_CONFIG_ENTRY, DOMAIN
from .entity import ShellyBlockEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for device."""
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id]

    # In roller mode the relay blocks exist but do not contain required info
    if (
        wrapper.model in ["SHSW-21", "SHSW-25"]
        and wrapper.device.settings["mode"] != "relay"
    ):
        return

    relay_blocks = [block for block in wrapper.device.blocks if block.type == "relay"]

    if not relay_blocks:
        return

    async_add_entities(RelaySwitch(wrapper, block) for block in relay_blocks)


class RelaySwitch(ShellyBlockEntity, SwitchEntity):
    """Switch that controls a relay block on Shelly devices."""

    def __init__(self, wrapper: ShellyDeviceWrapper, block: Block) -> None:
        """Initialize relay switch."""
        super().__init__(wrapper, block)
        self.control_result = None

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        if self.control_result:
            return self.control_result["ison"]

        return self.block.output

    async def async_turn_on(self, **kwargs):
        """Turn on relay."""
        self.control_result = await self.block.set_state(turn="on")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off relay."""
        self.control_result = await self.block.set_state(turn="off")
        self.async_write_ha_state()

    @callback
    def _update_callback(self):
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()
