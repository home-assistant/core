"""Support for Big Ass Fans switch."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from aiobafi6 import Device

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BAFEntity
from .models import BAFData


@dataclass
class BAFSwitchDescriptionMixin:
    """Required values for BAF sensors."""

    value_fn: Callable[[Device], bool | None]


@dataclass
class BAFSwitchDescription(
    SwitchEntityDescription,
    BAFSwitchDescriptionMixin,
):
    """Class describing BAF switch entities."""


BASE_SWITCHES = [
    BAFSwitchDescription(
        key="legacy_ir_remote_enable",
        name="Legacy IR Remote",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.legacy_ir_remote_enable),
    ),
    BAFSwitchDescription(
        key="led_indicators_enable",
        name="Led Indicators",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.led_indicators_enable),
    ),
]

AUTO_COMFORT_SWITCHES = [
    BAFSwitchDescription(
        key="comfort_heat_assist_enable",
        name="Auto Comfort Heat Assist",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.comfort_heat_assist_enable),
    ),
]

FAN_SWITCHES = [
    BAFSwitchDescription(
        key="fan_beep_enable",
        name="Beep",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.fan_beep_enable),
    ),
    BAFSwitchDescription(
        key="eco_enable",
        name="Eco Mode",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.eco_enable),
    ),
    BAFSwitchDescription(
        key="motion_sense_enable",
        name="Motion Sense",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.motion_sense_enable),
    ),
    BAFSwitchDescription(
        key="return_to_auto_enable",
        name="Return to Auto",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.return_to_auto_enable),
    ),
    BAFSwitchDescription(
        key="whoosh_enable",
        name="Whoosh",
        # Not a configuration switch
        value_fn=lambda device: cast(bool | None, device.whoosh_enable),
    ),
]


LIGHT_SWITCHES = [
    BAFSwitchDescription(
        key="light_dim_to_warm_enable",
        name="Dim to Warm",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.light_dim_to_warm_enable),
    ),
    BAFSwitchDescription(
        key="light_return_to_auto_enable",
        name="Light Return to Auto",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.light_return_to_auto_enable),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BAF fan switches."""
    data: BAFData = hass.data[DOMAIN][entry.entry_id]
    device = data.device
    descriptions: list[BAFSwitchDescription] = []
    descriptions.extend(BASE_SWITCHES)
    if device.has_fan:
        descriptions.extend(FAN_SWITCHES)
    if device.has_light:
        descriptions.extend(LIGHT_SWITCHES)
    if device.has_auto_comfort:
        descriptions.extend(AUTO_COMFORT_SWITCHES)
    async_add_entities(BAFSwitch(device, description) for description in descriptions)


class BAFSwitch(BAFEntity, SwitchEntity):
    """BAF switch component."""

    entity_description: BAFSwitchDescription

    def __init__(self, device: Device, description: BAFSwitchDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(device, f"{device.name} {description.name}")
        self._attr_unique_id = f"{self._device.mac_address}-{description.key}"

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        self._attr_is_on = self.entity_description.value_fn(self._device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        setattr(self._device, self.entity_description.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        setattr(self._device, self.entity_description.key, False)
