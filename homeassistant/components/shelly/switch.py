"""Switch for Shelly."""
from homeassistant.components.shelly import ShellyBlockEntity
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for device."""
    wrapper = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        RelaySwitch(wrapper, block)
        for block in wrapper.device.blocks
        if block.type == "relay"
    ]
    if entities:
        async_add_entities(entities)


class RelaySwitch(ShellyBlockEntity, SwitchEntity):
    """Switch that controls a relay block on Shelly devices."""

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        return self.block.output

    async def async_turn_on(self, **kwargs):
        """Turn on relay."""
        await self.block.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn off relay."""
        await self.block.turn_off()
