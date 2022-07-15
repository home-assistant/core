"""Support for Xiaomi buttons."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRFRESH_A1,
    MODEL_AIRFRESH_T2017,
)
from .device import XiaomiCoordinatedMiioEntity

ATTR_RESET_DUST_FILTER = "reset_dust_filter"
ATTR_RESET_UPPER_FILTER = "reset_upper_filter"


@dataclass
class XiaomiMiioButtonDescription(ButtonEntityDescription):
    """A class that describes button entities."""

    method_press: str = ""
    method_press_error_message: str = ""


BUTTON_TYPES = (
    XiaomiMiioButtonDescription(
        key=ATTR_RESET_DUST_FILTER,
        name="Reset Dust Filter",
        icon="mdi:air-filter",
        method_press="reset_dust_filter",
        method_press_error_message="Resetting the dust filter lifetime failed",
        entity_category=EntityCategory.CONFIG,
    ),
    XiaomiMiioButtonDescription(
        key=ATTR_RESET_UPPER_FILTER,
        name="Reset Upper Filter",
        icon="mdi:air-filter",
        method_press="reset_upper_filter",
        method_press_error_message="Resetting the upper filter lifetime failed.",
        entity_category=EntityCategory.CONFIG,
    ),
)

MODEL_TO_BUTTON_MAP: dict[str, tuple[str, ...]] = {
    MODEL_AIRFRESH_A1: (ATTR_RESET_DUST_FILTER,),
    MODEL_AIRFRESH_T2017: (
        ATTR_RESET_DUST_FILTER,
        ATTR_RESET_UPPER_FILTER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button from a config entry."""
    model = config_entry.data[CONF_MODEL]

    if model not in MODEL_TO_BUTTON_MAP:
        return

    entities = []
    buttons = MODEL_TO_BUTTON_MAP[model]
    unique_id = config_entry.unique_id
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for description in BUTTON_TYPES:
        if description.key not in buttons:
            continue

        entities.append(
            XiaomiGenericCoordinatedButton(
                f"{config_entry.title} {description.name}",
                device,
                config_entry,
                f"{description.key}_{unique_id}",
                coordinator,
                description,
            )
        )

    async_add_entities(entities)


class XiaomiGenericCoordinatedButton(XiaomiCoordinatedMiioEntity, ButtonEntity):
    """A button implementation for Xiaomi."""

    entity_description: XiaomiMiioButtonDescription

    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, name, device, entry, unique_id, coordinator, description):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id, coordinator)
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        method = getattr(self._device, self.entity_description.method_press)
        await self._try_command(
            self.entity_description.method_press_error_message,
            method,
        )
