"""Support for LiteJet switch."""

from typing import Any

from pylitejet import LiteJet, LiteJetError

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

ATTR_NUMBER = "number"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""

    system: LiteJet = hass.data[DOMAIN]

    entities = []
    for i in system.button_switches():
        name = await system.get_switch_name(i)
        entities.append(LiteJetSwitch(config_entry.entry_id, system, i, name))

    async_add_entities(entities, True)


class LiteJetSwitch(SwitchEntity):
    """Representation of a single LiteJet switch."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, entry_id: str, system: LiteJet, i: int, name: str) -> None:
        """Initialize a LiteJet switch."""
        self._lj = system
        self._index = i
        self._attr_is_on = False
        self._attr_unique_id = f"{entry_id}_{i}"
        self._attr_name = name

        # Keypad #1 has switches 1-6, #2 has 7-12, ...
        keypad_number = system.get_switch_keypad_number(i)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_keypad_{keypad_number}")},
            name=system.get_switch_keypad_name(i),
            manufacturer="Centralite",
            via_device=(DOMAIN, f"{entry_id}_mcp"),
        )

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        self._lj.on_switch_pressed(self._index, self._on_switch_pressed)
        self._lj.on_switch_released(self._index, self._on_switch_released)
        self._lj.on_connected_changed(self._on_connected_changed)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self._lj.unsubscribe(self._on_switch_pressed)
        self._lj.unsubscribe(self._on_switch_released)
        self._lj.unsubscribe(self._on_connected_changed)

    def _on_switch_pressed(self) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    def _on_switch_released(self) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()

    def _on_connected_changed(self, connected: bool, reason: str) -> None:
        self._attr_available = connected
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device-specific state attributes."""
        return {ATTR_NUMBER: self._index}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Press the switch."""
        try:
            await self._lj.press_switch(self._index)
        except LiteJetError as exc:
            raise HomeAssistantError from exc

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Release the switch."""
        try:
            await self._lj.release_switch(self._index)
        except LiteJetError as exc:
            raise HomeAssistantError from exc
