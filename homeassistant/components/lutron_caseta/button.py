"""Support for pico and keypad buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDevice
from .const import DOMAIN as CASETA_DOMAIN
from .device_trigger import (
    LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP,
    _lutron_model_to_device_type,
)
from .models import LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lutron pico and keypad buttons."""
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data.bridge
    button_devices = bridge.get_buttons()

    async_add_entities(
        LutronCasetaButton(button_devices[button_device_id], data)
        for button_device_id in button_devices
    )


class LutronCasetaButton(LutronCasetaDevice, ButtonEntity):
    """Representation of a Lutron pico and keypad button."""

    def __init__(self, device, data):
        """Init a button entity."""

        super().__init__(device, data)
        self._enabled_default = True

        parent_device_info = data.device_info_by_device_id.get(device["parent_device"])

        if not (device_name := device.get("device_name")):
            # device name (button name) is missing, probably a caseta pico
            # try to get the name using the button number from the triggers
            # disable the button by default
            self._enabled_default = False
            keypad_device = self._smartbridge.get_devices()[device["parent_device"]]
            button_numbers = LEAP_TO_DEVICE_TYPE_SUBTYPE_MAP.get(
                _lutron_model_to_device_type(
                    keypad_device["model"], keypad_device["type"]
                ),
                {},
            )
            device_name = button_numbers.get(
                int(device["button_number"]),
                f"button {device['button_number']}",
            )

        # Append the child device name to the end of the parent keypad name to create the entity name
        self._attr_name = f'{parent_device_info["name"]} {device_name}'
        # Set the device_info to the same as the Parent Keypad
        # The entities will be nested inside the keypad device
        self._attr_device_info = parent_device_info

    async def async_press(self) -> None:
        """Send a button press event."""
        await self._smartbridge.tap_button(self.device_id)

    @property
    def serial(self):
        """Buttons shouldn't have serial numbers, Return None."""
        return None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return the default enabled status of the entity."""
        return self._enabled_default
