"""Support for Big Ass Fans number."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from aiobafi6 import Device

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BAFConfigEntry
from .const import HALF_DAY_SECS, ONE_DAY_SECS, ONE_MIN_SECS, SPEED_RANGE
from .entity import BAFDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class BAFNumberDescription(NumberEntityDescription):
    """Class describing BAF sensor entities."""

    value_fn: Callable[[Device], int | None]


AUTO_COMFORT_NUMBER_DESCRIPTIONS = (
    BAFNumberDescription(
        key="comfort_min_speed",
        translation_key="comfort_min_speed",
        native_step=1,
        native_min_value=0,
        native_max_value=SPEED_RANGE[1] - 1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(int | None, device.comfort_min_speed),
        mode=NumberMode.BOX,
    ),
    BAFNumberDescription(
        key="comfort_max_speed",
        translation_key="comfort_max_speed",
        native_step=1,
        native_min_value=1,
        native_max_value=SPEED_RANGE[1],
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(int | None, device.comfort_max_speed),
        mode=NumberMode.BOX,
    ),
    BAFNumberDescription(
        key="comfort_heat_assist_speed",
        translation_key="comfort_heat_assist_speed",
        native_step=1,
        native_min_value=SPEED_RANGE[0],
        native_max_value=SPEED_RANGE[1],
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(int | None, device.comfort_heat_assist_speed),
        mode=NumberMode.BOX,
    ),
)

FAN_NUMBER_DESCRIPTIONS = (
    BAFNumberDescription(
        key="return_to_auto_timeout",
        translation_key="return_to_auto_timeout",
        native_step=1,
        native_min_value=ONE_MIN_SECS,
        native_max_value=HALF_DAY_SECS,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda device: cast(int | None, device.return_to_auto_timeout),
        mode=NumberMode.SLIDER,
    ),
    BAFNumberDescription(
        key="motion_sense_timeout",
        translation_key="motion_sense_timeout",
        native_step=1,
        native_min_value=ONE_MIN_SECS,
        native_max_value=ONE_DAY_SECS,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda device: cast(int | None, device.motion_sense_timeout),
        mode=NumberMode.SLIDER,
    ),
)

LIGHT_NUMBER_DESCRIPTIONS = (
    BAFNumberDescription(
        key="light_return_to_auto_timeout",
        translation_key="light_return_to_auto_timeout",
        native_step=1,
        native_min_value=ONE_MIN_SECS,
        native_max_value=HALF_DAY_SECS,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda device: cast(int | None, device.light_return_to_auto_timeout),
        mode=NumberMode.SLIDER,
    ),
    BAFNumberDescription(
        key="light_auto_motion_timeout",
        translation_key="light_auto_motion_timeout",
        native_step=1,
        native_min_value=ONE_MIN_SECS,
        native_max_value=ONE_DAY_SECS,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda device: cast(int | None, device.light_auto_motion_timeout),
        mode=NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BAFConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BAF numbers."""
    device = entry.runtime_data
    descriptions: list[BAFNumberDescription] = []
    if device.has_fan:
        descriptions.extend(FAN_NUMBER_DESCRIPTIONS)
    if device.has_light:
        descriptions.extend(LIGHT_NUMBER_DESCRIPTIONS)
    if device.has_auto_comfort:
        descriptions.extend(AUTO_COMFORT_NUMBER_DESCRIPTIONS)
    async_add_entities(BAFNumber(device, description) for description in descriptions)


class BAFNumber(BAFDescriptionEntity, NumberEntity):
    """BAF number."""

    entity_description: BAFNumberDescription

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        if (value := self.entity_description.value_fn(self._device)) is not None:
            self._attr_native_value = float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        setattr(self._device, self.entity_description.key, int(value))
