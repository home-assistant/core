"""Wyoming switch entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import restore_state
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devices import SatelliteDevice
from .entity import WyomingSatelliteEntity

if TYPE_CHECKING:
    from .models import DomainDataItem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP switch entities."""
    domain_data: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_device(device: SatelliteDevice) -> None:
        """Add device."""
        async_add_entities([WyomingSatelliteEnabledSwitch(device)])

    domain_data.satellite_devices.async_add_new_device_listener(async_add_device)

    async_add_entities(
        [
            WyomingSatelliteEnabledSwitch(device)
            for device in domain_data.satellite_devices
        ]
    )


class WyomingSatelliteEnabledSwitch(
    WyomingSatelliteEntity, restore_state.RestoreEntity, SwitchEntity
):
    """Entity to represent voip is allowed."""

    _attr_is_on = True

    entity_description = SwitchEntityDescription(
        key="satellite_enabled",
        translation_key="satellite_enabled",
        entity_category=EntityCategory.CONFIG,
    )

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        self._attr_is_on = state is not None and state.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        self._attr_is_on = True
        self._device.set_is_enabled(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        self._attr_is_on = False
        self._device.set_is_enabled(False)
        self.async_write_ha_state()
