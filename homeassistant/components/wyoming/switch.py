"""Wyoming switch entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import restore_state
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WyomingSatelliteEntity

if TYPE_CHECKING:
    from .models import DomainDataItem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP switch entities."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    # Setup is only forwarded for satellites
    assert item.satellite is not None

    async_add_entities([WyomingSatelliteMuteSwitch(item.satellite.device)])


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
        self._device.is_muted = self._attr_is_on

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
