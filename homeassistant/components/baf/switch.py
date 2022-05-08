"""Support for Big Ass Fans switch."""
from __future__ import annotations

from typing import Any, cast

from aiobafi6 import Device

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BAFEntity
from .models import BAFData

PROPERTY_CATEGORY = {
    "legacy_ir_remote_enable": EntityCategory.CONFIG,
    "led_indicators_enable": EntityCategory.CONFIG,
    "comfort_heat_assist_enable": EntityCategory.CONFIG,
    "fan_beep_enable": EntityCategory.CONFIG,
    "eco_enable": EntityCategory.CONFIG,
    "motion_sense_enable": EntityCategory.CONFIG,
    "return_to_auto_enable": EntityCategory.CONFIG,
    "light_dim_to_warm_enable": EntityCategory.CONFIG,
    "light_return_to_auto_enable": EntityCategory.CONFIG,
}

BASE_PROPERTY_NAMES = {
    "legacy_ir_remote_enable": "Legacy IR Remote",
    "led_indicators_enable": "Led Indicators",
}

BASE_SWITCHES = [
    SwitchEntityDescription(
        key=key, name=name, entity_category=PROPERTY_CATEGORY.get(key)
    )
    for key, name in BASE_PROPERTY_NAMES.items()
]

FAN_PROPERTY_NAMES = {
    "comfort_heat_assist_enable": "Auto Comfort Heat Assist",
    "fan_beep_enable": "Beep",
    "eco_enable": "Eco Mode",
    "motion_sense_enable": "Motion Sense",
    "return_to_auto_enable": "Return to Auto",
    "whoosh_enable": "Whoosh",
}

FAN_SWITCHES = [
    SwitchEntityDescription(
        key=key, name=name, entity_category=PROPERTY_CATEGORY.get(key)
    )
    for key, name in FAN_PROPERTY_NAMES.items()
]

LIGHT_PROPERTY_NAMES = {
    "light_dim_to_warm_enable": "Dim to Warm",
    "light_return_to_auto_enable": "Light Return to Auto",
}

LIGHT_SWITCHES = [
    SwitchEntityDescription(
        key=key, name=name, entity_category=PROPERTY_CATEGORY.get(key)
    )
    for key, name in LIGHT_PROPERTY_NAMES.items()
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BAF fan switches."""
    data: BAFData = hass.data[DOMAIN][entry.entry_id]
    device = data.device
    descriptions: list[SwitchEntityDescription] = []
    descriptions.extend(BASE_SWITCHES)
    if device.has_fan:
        descriptions.extend(FAN_SWITCHES)
    if device.has_light:
        descriptions.extend(LIGHT_SWITCHES)
    async_add_entities(BAFSwitch(device, description) for description in descriptions)


class BAFSwitch(BAFEntity, SwitchEntity):
    """BAF switch component."""

    entity_description: SwitchEntityDescription

    def __init__(self, device: Device, description: SwitchEntityDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(device, f"{device.name} {description.name}")
        self._attr_unique_id = f"{self._device.mac_address}-{description.key}"

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = cast(
            bool, getattr(self._device, self.entity_description.key)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        setattr(self._device, self.entity_description.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        setattr(self._device, self.entity_description.key, False)
