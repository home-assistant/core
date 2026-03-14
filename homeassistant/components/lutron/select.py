"""Support for Lutron selects."""

from __future__ import annotations

from pylutron import Button, Keypad, Led, Lutron

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LutronConfigEntry
from .entity import LutronKeypad

_LED_STATE_MAP = {
    Led.LED_OFF: "Off",
    Led.LED_ON: "On",
    Led.LED_SLOW_FLASH: "Slow Flash",
    Led.LED_FAST_FLASH: "Fast Flash",
}

_LED_NAME_MAP = {v: k for k, v in _LED_STATE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron select platform."""
    entry_data = config_entry.runtime_data
    entities: list[SelectEntity] = []

    # Add the indicator LEDs for scenes (keypad buttons)
    for area_name, keypad, scene, led in entry_data.scenes:
        if led is not None:
            entities.append(
                LutronLedSelect(area_name, keypad, scene, led, entry_data.client)
            )
    async_add_entities(entities, True)


class LutronLedSelect(LutronKeypad, SelectEntity):
    """Representation of a Lutron Keypad LED."""

    _lutron_device: Led
    _attr_options = list(_LED_NAME_MAP.keys())

    def __init__(
        self,
        area_name: str,
        keypad: Keypad,
        scene_device: Button,
        led_device: Led,
        controller: Lutron,
    ) -> None:
        """Initialize the switch."""
        super().__init__(area_name, led_device, controller, keypad)
        self._keypad_name = keypad.name
        self._attr_name = f"{scene_device.name} LED"

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return _LED_STATE_MAP.get(self._lutron_device.last_state)

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._lutron_device.state = _LED_NAME_MAP[option]

    def _request_state(self) -> None:
        """Request the state from the device."""
        _ = self._lutron_device.state

    def _update_attrs(self) -> None:
        """Update the state attributes."""
