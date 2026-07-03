"""Support for KEBA charging station switch."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KebaConfigEntry, KebaHandler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KebaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KEBA charging station switch platform."""
    keba = entry.runtime_data
    async_add_entities([KebaSwitch(keba, "Charging Enabled", "charging_enabled")])


class KebaSwitch(SwitchEntity):
    """The entity class for KEBA charging station enable/disable switch."""

    _attr_should_poll = False

    def __init__(self, keba: KebaHandler, name: str, entity_type: str) -> None:
        """Initialize the KEBA switch."""
        self._keba = keba
        self._attr_is_on = True
        self._attr_name = f"{keba.device_name} {name}"
        self._attr_unique_id = f"{keba.device_id}_{entity_type}"

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable EV charging."""
        await self._keba.async_enable_ev()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable EV charging."""
        await self._keba.async_disable_ev()

    async def async_update(self) -> None:
        """Update switch state from device data."""
        self._attr_is_on = self._keba.get_value("Enable user") == 1

    def update_callback(self) -> None:
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    @override
    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        self.async_on_remove(self._keba.add_update_listener(self.update_callback))
