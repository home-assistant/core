"""Support for LiteJet switch."""
from typing import Any

from pylitejet import LiteJet, LiteJetError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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

    def __init__(self, entry_id, lj, i, name):  # pylint: disable=invalid-name
        """Initialize a LiteJet switch."""
        self._entry_id = entry_id
        self._lj = lj
        self._index = i
        self._attr_is_on = False
        self._attr_name = name

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

    def _on_switch_pressed(self):
        self._attr_is_on = True
        self.schedule_update_ha_state()

    def _on_switch_released(self):
        self._attr_is_on = False
        self.schedule_update_ha_state()

    def _on_connected_changed(self, connected: bool, reason: str) -> None:
        self._attr_available = connected
        self.schedule_update_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for this switch."""
        return f"{self._entry_id}_{self._index}"

    @property
    def extra_state_attributes(self):
        """Return the device-specific state attributes."""
        return {ATTR_NUMBER: self._index}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Press the switch."""
        try:
            await self._lj.press_switch(self._index)
        except LiteJetError as exc:
            raise HomeAssistantError() from exc

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Release the switch."""
        try:
            await self._lj.release_switch(self._index)
        except LiteJetError as exc:
            raise HomeAssistantError() from exc

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Switches are only enabled by explicit user choice."""
        return False
