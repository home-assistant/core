"""Support for Big Ass Fans switch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from aiobafi6 import Device

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BAFConfigEntry
from .entity import BAFDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class BAFSwitchDescription(
    SwitchEntityDescription,
):
    """Class describing BAF switch entities."""

    value_fn: Callable[[Device], bool | None]


BASE_SWITCHES = [
    BAFSwitchDescription(
        key="legacy_ir_remote_enable",
        translation_key="legacy_ir_remote_enable",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.legacy_ir_remote_enable),
    ),
    BAFSwitchDescription(
        key="led_indicators_enable",
        translation_key="led_indicators_enable",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.led_indicators_enable),
    ),
]

AUTO_COMFORT_SWITCHES = [
    BAFSwitchDescription(
        key="comfort_heat_assist_enable",
        translation_key="comfort_heat_assist_enable",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.comfort_heat_assist_enable),
    ),
]

FAN_SWITCHES = [
    BAFSwitchDescription(
        key="fan_beep_enable",
        translation_key="fan_beep_enable",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.fan_beep_enable),
    ),
    BAFSwitchDescription(
        key="eco_enable",
        translation_key="eco_enable",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.eco_enable),
    ),
    BAFSwitchDescription(
        key="motion_sense_enable",
        translation_key="motion_sense_enable",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.motion_sense_enable),
    ),
    BAFSwitchDescription(
        key="return_to_auto_enable",
        translation_key="return_to_auto_enable",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.return_to_auto_enable),
    ),
    BAFSwitchDescription(
        key="whoosh_enable",
        translation_key="whoosh_enable",
        # Not a configuration switch
        value_fn=lambda device: cast(bool | None, device.whoosh_enable),
    ),
]


LIGHT_SWITCHES = [
    BAFSwitchDescription(
        key="light_dim_to_warm_enable",
        translation_key="light_dim_to_warm_enable",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.light_dim_to_warm_enable),
    ),
    BAFSwitchDescription(
        key="light_return_to_auto_enable",
        translation_key="light_return_to_auto_enable",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(bool | None, device.light_return_to_auto_enable),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BAFConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BAF fan switches."""
    device = entry.runtime_data
    descriptions: list[BAFSwitchDescription] = []
    descriptions.extend(BASE_SWITCHES)
    if device.has_fan:
        descriptions.extend(FAN_SWITCHES)
    if device.has_light:
        descriptions.extend(LIGHT_SWITCHES)
    if device.has_auto_comfort:
        descriptions.extend(AUTO_COMFORT_SWITCHES)
    async_add_entities(BAFSwitch(device, description) for description in descriptions)


class BAFSwitch(BAFDescriptionEntity, SwitchEntity):
    """BAF switch component."""

    entity_description: BAFSwitchDescription

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
