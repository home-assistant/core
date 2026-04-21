"""Wyoming switch entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import restore_state
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import WyomingSatelliteEntity
from .models import WyomingConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WyomingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VoIP switch entities."""
    item = config_entry.runtime_data

    # Setup is only forwarded for satellites
    assert item.device is not None

    async_add_entities([WyomingSatelliteMuteSwitch(item.device)])


class WyomingSatelliteMuteSwitch(
    WyomingSatelliteEntity, restore_state.RestoreEntity, SwitchEntity
):
    """Entity to represent if satellite is muted."""

    entity_description = SwitchEntityDescription(
        key="mute",
        translation_key="mute",
        entity_category=EntityCategory.CONFIG,
    )

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()

        # Default to off
        self._attr_is_on = (state is not None) and (state.state == STATE_ON)
        self._device.set_is_muted(self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        self._attr_is_on = True
        self.async_write_ha_state()
        self._device.set_is_muted(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        self._attr_is_on = False
        self.async_write_ha_state()
        self._device.set_is_muted(False)
