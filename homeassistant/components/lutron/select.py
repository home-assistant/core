"""Support for Lutron selects."""

from __future__ import annotations

from pylutron import Button, Keypad, Led, Lutron

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LutronConfigEntry
from .entity import LutronKeypad

_LED_STATE_TO_OPTION = {
    Led.LED_OFF: "off",
    Led.LED_ON: "on",
    Led.LED_SLOW_FLASH: "slow_flash",
    Led.LED_FAST_FLASH: "fast_flash",
}

_LED_OPTION_TO_STATE = {v: k for k, v in _LED_STATE_TO_OPTION.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron select platform."""
    entry_data = config_entry.runtime_data

    # Add the indicator LEDs for scenes (keypad buttons)
    async_add_entities(
        [
            LutronLedSelect(area_name, keypad, scene, led, entry_data.client)
            for area_name, keypad, scene, led in entry_data.scenes
            if led is not None
        ],
        True,
    )


class LutronLedSelect(LutronKeypad, SelectEntity):
    """Representation of a Lutron Keypad LED."""

    _lutron_device: Led
    _attr_options = list(_LED_STATE_TO_OPTION.values())
    _attr_translation_key = "led_state"

    def __init__(
        self,
        area_name: str,
        keypad: Keypad,
        scene_device: Button,
        led_device: Led,
        controller: Lutron,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(area_name, led_device, controller, keypad)
        self._attr_name = f"{scene_device.name} LED"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return _LED_STATE_TO_OPTION.get(self._lutron_device.last_state)

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._lutron_device.state = _LED_OPTION_TO_STATE[option]

    def _request_state(self) -> None:
        """Request the state from the device."""
        _ = self._lutron_device.state
