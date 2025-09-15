"""Binary sensor support for Apple TV."""

from __future__ import annotations

from pyatv.const import KeyboardFocusState
from pyatv.interface import AppleTV, KeyboardListener

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AppleTvConfigEntry
from .entity import AppleTVEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AppleTvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Load Apple TV binary sensor based on a config entry."""
    # apple_tv config entries always have a unique id
    assert config_entry.unique_id is not None
    name: str = config_entry.data[CONF_NAME]
    manager = config_entry.runtime_data
    async_add_entities([AppleTVKeyboardFocused(name, config_entry.unique_id, manager)])


class AppleTVKeyboardFocused(AppleTVEntity, BinarySensorEntity, KeyboardListener):
    """Binary sensor for Text input focused."""

    _attr_translation_key = "keyboard_focused"

    @callback
    def async_device_connected(self, atv: AppleTV) -> None:
        """Handle when connection is made to device."""
        # Listen to keyboard updates
        atv.keyboard.listener = self
        # Set initial state based on current focus state
        self._update_state(atv.keyboard.text_focus_state == KeyboardFocusState.Focused)

    @callback
    def async_device_disconnected(self) -> None:
        """Handle when connection was lost to device."""
        self._attr_is_on = False
        self._update_state(False)

    def focusstate_update(
        self, old_state: KeyboardFocusState, new_state: KeyboardFocusState
    ) -> None:
        """Update keyboard state when it changes.

        This is a callback function from pyatv.interface.KeyboardListener.
        """
        self._update_state(new_state == KeyboardFocusState.Focused)

    def _update_state(self, new_state: bool) -> None:
        """Update and report."""
        self._attr_is_on = new_state
        self.async_write_ha_state()
