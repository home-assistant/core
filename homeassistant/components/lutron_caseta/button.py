"""Support for pico and keypad buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDevice
from .const import DOMAIN as CASETA_DOMAIN
from .models import LutronButton, LutronCasetaData, LutronKeypad


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lutron pico and keypad buttons."""
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    buttons = data.keypad_data.buttons
    keypads = data.keypad_data.keypads

    async_add_entities(
        LutronCasetaButton(button, keypads[button["parent_keypad"]], data)
        for button in buttons.values()
    )


class LutronCasetaButton(LutronCasetaDevice, ButtonEntity):
    """Representation of a Lutron pico and keypad button."""

    def __init__(
        self,
        button: LutronButton,
        keypad: LutronKeypad,
        data: LutronCasetaData,
    ) -> None:
        """Init a button entity."""
        bridge_button = data.bridge.buttons[button["lutron_device_id"]]
        super().__init__(bridge_button, data)

        self._attr_entity_registry_enabled_default = button["enabled_default"]
        self._attr_name = (
            f'{keypad["area_name"]} {keypad["name"]} {button["button_name"]}'
        )
        self._attr_device_info = keypad["device_info"]

    async def async_press(self) -> None:
        """Send a button press event."""
        await self._smartbridge.tap_button(self.device_id)

    @property
    def serial(self):
        """Buttons shouldn't have serial numbers, Return None."""
        return None
