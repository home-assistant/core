"""Switch for Shelly."""
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


class RelaySwitch(SwitchEntity):
    """Switch that controls a relay block on Shelly devices."""

    def __init__(self, wrapper, block):
        """Initialize Shelly entity."""
        self.wrapper = wrapper
        self.block = block

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        return self.block.output

    @property
    def name(self):
        """Name of entity."""
        return f"{self.wrapper.name} - {self.block.description}"

    @property
    def should_poll(self):
        """If device should be polled."""
        return False

    @property
    def device_info(self):
        """Device info."""
        return self.wrapper.device_info

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return f"{self.wrapper.mac}-{self.block.index}"

    async def async_added_to_hass(self):
        """When entity is added to HASS."""
        self.async_on_remove(self.wrapper.async_add_listener(self.async_write_ha_state))

    async def async_turn_on(self, **kwargs):
        """Turn on relay."""
        await self.block.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn off relay."""
        await self.block.turn_off()

    async def async_update(self):
        """Update entity with latest info."""
        await self.wrapper.async_request_refresh()
