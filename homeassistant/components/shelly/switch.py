"""Switch for Shelly."""
from aioshelly import RelayBlock

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from . import ShellyBlockEntity, ShellyDeviceWrapper
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for device."""
    wrapper = hass.data[DOMAIN][config_entry.entry_id]

    if wrapper.model == "SHSW-25" and wrapper.device.settings["mode"] != "relay":
        return

    relay_blocks = [block for block in wrapper.device.blocks if block.type == "relay"]

    if not relay_blocks:
        return

    multiple_blocks = len(relay_blocks) > 1
    async_add_entities(
        RelaySwitch(wrapper, block, multiple_blocks=multiple_blocks)
        for block in relay_blocks
    )


class RelaySwitch(ShellyBlockEntity, SwitchEntity):
    """Switch that controls a relay block on Shelly devices."""

    def __init__(
        self, wrapper: ShellyDeviceWrapper, block: RelayBlock, multiple_blocks
    ) -> None:
        """Initialize relay switch."""
        super().__init__(wrapper, block)
        self.multiple_blocks = multiple_blocks
        self.control_result = None

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        if self.control_result:
            return self.control_result["ison"]

        return self.block.output

    @property
    def device_info(self):
        """Device info."""
        if not self.multiple_blocks:
            return super().device_info

        # If a device has multiple relays, we want to expose as separate device
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.wrapper.mac, self.block.index)},
            "via_device": (DOMAIN, self.wrapper.mac),
        }

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
