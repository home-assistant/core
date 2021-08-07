"""Switch for Shelly."""
from __future__ import annotations

from typing import Any, cast

from aioshelly import Block

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ShellyDeviceWrapper
from .const import COAP, DATA_CONFIG_ENTRY, DOMAIN
from .entity import ShellyBlockEntity
from .utils import async_remove_shelly_entity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""
    wrapper = hass.data[DOMAIN][DATA_CONFIG_ENTRY][config_entry.entry_id][COAP]

    # In roller mode the relay blocks exist but do not contain required info
    if (
        wrapper.model in ["SHSW-21", "SHSW-25"]
        and wrapper.device.settings["mode"] != "relay"
    ):
        return

    relay_blocks = []
    for block in wrapper.device.blocks:
        if block.type == "relay":
            appliance_type = wrapper.device.settings["relays"][int(block.channel)].get(
                "appliance_type"
            )
            if not appliance_type or appliance_type.lower() != "light":
                relay_blocks.append(block)
                unique_id = (
                    f'{wrapper.device.shelly["mac"]}-{block.type}_{block.channel}'
                )
                await async_remove_shelly_entity(
                    hass,
                    "light",
                    unique_id,
                )

    if not relay_blocks:
        return

    async_add_entities(RelaySwitch(wrapper, block) for block in relay_blocks)


class RelaySwitch(ShellyBlockEntity, SwitchEntity):
    """Switch that controls a relay block on Shelly devices."""

    def __init__(self, wrapper: ShellyDeviceWrapper, block: Block) -> None:
        """Initialize relay switch."""
        super().__init__(wrapper, block)
        self.control_result: dict[str, Any] | None = None

    @property
    def is_on(self) -> bool:
        """If switch is on."""
        if self.control_result:
            return cast(bool, self.control_result["ison"])

        return bool(self.block.output)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on relay."""
        self.control_result = await self.set_state(turn="on")
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off relay."""
        self.control_result = await self.set_state(turn="off")
        self.async_write_ha_state()

    @callback
    def _update_callback(self) -> None:
        """When device updates, clear control result that overrides state."""
        self.control_result = None
        super()._update_callback()
