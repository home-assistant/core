"""Support for WiZ effect speed numbers."""
from __future__ import annotations

from pywizlight import PilotBuilder
from pywizlight.bulblibrary import BulbClass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WizEntity
from .models import WizData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the wiz speed number."""
    wiz_data: WizData = hass.data[DOMAIN][entry.entry_id]
    if wiz_data.bulb.bulbtype.bulb_type != BulbClass.SOCKET:
        async_add_entities([WizSpeedNumber(wiz_data, entry.title)])


class WizSpeedNumber(WizEntity, NumberEntity):
    """Defines a WiZ speed number."""

    _attr_min_value = 20
    _attr_max_value = 200
    _attr_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:speedometer"

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_value = self._device.state.get_speed()

    async def async_set_value(self, value: float) -> None:
        """Set the speed value."""
        await self._device.turn_on(PilotBuilder(speed=value))
        await self.coordinator.async_request_refresh()
