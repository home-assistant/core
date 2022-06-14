"""Support for Big Ass Fans number."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional, cast

from aiobafi6 import Device

from homeassistant import config_entries
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import TIME_SECONDS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, HALF_DAY_SECS, ONE_DAY_SECS, ONE_MIN_SECS, SPEED_RANGE
from .entity import BAFEntity
from .models import BAFData


@dataclass
class BAFNumberDescriptionMixin:
    """Required values for BAF sensors."""

    value_fn: Callable[[Device], int | None]
    mode: NumberMode


@dataclass
class BAFNumberDescription(NumberEntityDescription, BAFNumberDescriptionMixin):
    """Class describing BAF sensor entities."""


AUTO_COMFORT_NUMBER_DESCRIPTIONS = (
    BAFNumberDescription(
        key="comfort_min_speed",
        name="Auto Comfort Minimum Speed",
        native_min_value=0,
        native_max_value=SPEED_RANGE[1] - 1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(Optional[int], device.comfort_min_speed),
        mode=NumberMode.BOX,
    ),
    BAFNumberDescription(
        key="comfort_max_speed",
        name="Auto Comfort Maximum Speed",
        native_min_value=1,
        native_max_value=SPEED_RANGE[1],
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(Optional[int], device.comfort_max_speed),
        mode=NumberMode.BOX,
    ),
    BAFNumberDescription(
        key="comfort_heat_assist_speed",
        name="Auto Comfort Heat Assist Speed",
        native_min_value=SPEED_RANGE[0],
        native_max_value=SPEED_RANGE[1],
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda device: cast(Optional[int], device.comfort_heat_assist_speed),
        mode=NumberMode.BOX,
    ),
)

FAN_NUMBER_DESCRIPTIONS = (
    BAFNumberDescription(
        key="return_to_auto_timeout",
        name="Return to Auto Timeout",
        native_min_value=ONE_MIN_SECS,
        native_max_value=HALF_DAY_SECS,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=TIME_SECONDS,
        value_fn=lambda device: cast(Optional[int], device.return_to_auto_timeout),
        mode=NumberMode.SLIDER,
    ),
    BAFNumberDescription(
        key="motion_sense_timeout",
        name="Motion Sense Timeout",
        native_min_value=ONE_MIN_SECS,
        native_max_value=ONE_DAY_SECS,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=TIME_SECONDS,
        value_fn=lambda device: cast(Optional[int], device.motion_sense_timeout),
        mode=NumberMode.SLIDER,
    ),
)

LIGHT_NUMBER_DESCRIPTIONS = (
    BAFNumberDescription(
        key="light_return_to_auto_timeout",
        name="Light Return to Auto Timeout",
        native_min_value=ONE_MIN_SECS,
        native_max_value=HALF_DAY_SECS,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=TIME_SECONDS,
        value_fn=lambda device: cast(
            Optional[int], device.light_return_to_auto_timeout
        ),
        mode=NumberMode.SLIDER,
    ),
    BAFNumberDescription(
        key="light_auto_motion_timeout",
        name="Light Motion Sense Timeout",
        native_min_value=ONE_MIN_SECS,
        native_max_value=ONE_DAY_SECS,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=TIME_SECONDS,
        value_fn=lambda device: cast(Optional[int], device.light_auto_motion_timeout),
        mode=NumberMode.SLIDER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BAF numbers."""
    data: BAFData = hass.data[DOMAIN][entry.entry_id]
    device = data.device
    descriptions: list[BAFNumberDescription] = []
    if device.has_fan:
        descriptions.extend(FAN_NUMBER_DESCRIPTIONS)
    if device.has_light:
        descriptions.extend(LIGHT_NUMBER_DESCRIPTIONS)
    if device.has_auto_comfort:
        descriptions.extend(AUTO_COMFORT_NUMBER_DESCRIPTIONS)
    async_add_entities(BAFNumber(device, description) for description in descriptions)


class BAFNumber(BAFEntity, NumberEntity):
    """BAF number."""

    entity_description: BAFNumberDescription

    def __init__(self, device: Device, description: BAFNumberDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(device, f"{device.name} {description.name}")
        self._attr_unique_id = f"{self._device.mac_address}-{description.key}"
        self._attr_mode = description.mode

    @callback
    def _async_update_attrs(self) -> None:
        """Update attrs from device."""
        if (value := self.entity_description.value_fn(self._device)) is not None:
            self._attr_native_value = float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        setattr(self._device, self.entity_description.key, int(value))
