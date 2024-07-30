"""Support for pico and keypad buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDevice
from .models import LutronCasetaButtonDevice, LutronCasetaConfigEntry, LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronCasetaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lutron pico and keypad buttons."""
    data = config_entry.runtime_data
    async_add_entities(
        LutronCasetaButton(data, button_device) for button_device in data.button_devices
    )


class LutronCasetaButton(LutronCasetaDevice, ButtonEntity):
    """Representation of a Lutron pico and keypad button."""

    def __init__(
        self,
        data: LutronCasetaData,
        button_device: LutronCasetaButtonDevice,
    ) -> None:
        """Init a button entity."""
        super().__init__(button_device.device, data)
        self._attr_entity_registry_enabled_default = button_device.has_device_name
        self._attr_name = button_device.full_name
        self._attr_device_info = button_device.parent_device_info

    async def async_press(self) -> None:
        """Send a button press event."""
        await self._smartbridge.tap_button(self.device_id)

    @property
    def serial(self):
        """Buttons shouldn't have serial numbers, Return None."""
        return None
