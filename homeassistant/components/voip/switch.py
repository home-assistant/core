"""VoIP switch entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, restore_state
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import VoIPEntity

if TYPE_CHECKING:
    from . import DomainData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP switch entities."""
    domain_data: DomainData = hass.data[DOMAIN]

    @callback
    def async_add_device(device: dr.DeviceEntry) -> None:
        """Add device."""
        async_add_entities([VoIPCallAllowedSwitch(device)])

    domain_data.devices.async_add_new_device_listener(async_add_device)

    async_add_entities(
        [
            VoIPCallAllowedSwitch(device)
            for device in dr.async_entries_for_config_entry(
                dr.async_get(hass),
                config_entry.entry_id,
            )
        ]
    )


class VoIPCallAllowedSwitch(VoIPEntity, restore_state.RestoreEntity, SwitchEntity):
    """Entity to represent voip is allowed."""

    entity_description = SwitchEntityDescription(
        key="allow_call", translation_key="allow_call"
    )

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        self._attr_is_on = state is not None and state.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        self._attr_is_on = False
        self.async_write_ha_state()
