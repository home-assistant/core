"""Support for pico and keypad buttons."""

from typing import Any, override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LutronCasetaEntity
from .models import LutronCasetaConfigEntry, LutronCasetaData
from .util import enumerate_buttons


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronCasetaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lutron pico and keypad buttons."""
    data = config_entry.runtime_data

    # Legacy naming: the parent keypad name is baked into the entity name
    # and cannot change without breaking existing entity ids
    async_add_entities(
        LutronCasetaButton(
            hass,
            device,
            data,
            f"{device_info.get('name')} {button_name}",
            enabled_default,
            device_info,
        )
        for device, button_name, enabled_default, device_info in enumerate_buttons(data)
    )


class LutronCasetaButton(LutronCasetaEntity, ButtonEntity):
    """Representation of a Lutron pico and keypad button."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: dict[str, Any],
        data: LutronCasetaData,
        full_name: str,
        enabled_default: bool,
        device_info: DeviceInfo,
    ) -> None:
        """Init a button entity."""
        super().__init__(hass, device, data)
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_name = full_name
        self._attr_device_info = device_info

    @override
    async def async_press(self) -> None:
        """Send a button press event."""
        await self._smartbridge.tap_button(self.device_id)

    @property
    @override
    def serial(self):
        """Buttons shouldn't have serial numbers, Return None."""
        return None
