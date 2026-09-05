"""Support for WiZ effect speed numbers."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import cast, override

from pywizlight import wizlight

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WizConfigEntry, WizData
from .entity import WizEntity, get_wiz_state


@dataclass(frozen=True, kw_only=True)
class WizNumberEntityDescription(NumberEntityDescription):
    """Class to describe a WiZ number entity."""

    required_feature: str
    set_value_fn: Callable[[wizlight, int], Coroutine[None, None, None]]
    value_fn: Callable[[wizlight], int | None]
    # Optional runtime support check used instead of required_feature.
    supported_fn: Callable[[wizlight], bool] | None = None


async def _async_set_speed(device: wizlight, speed: int) -> None:
    await device.set_speed(speed)


async def _async_set_ratio(device: wizlight, ratio: int) -> None:
    await device.set_ratio(ratio)


def _get_speed(device: wizlight) -> int | None:
    """Return the effect speed."""
    return (
        cast(int | None, state.get_speed())
        if (state := get_wiz_state(device))
        else None
    )


def _get_ratio(device: wizlight) -> int | None:
    """Return the dual head ratio."""
    return (
        cast(int | None, state.get_ratio())
        if (state := get_wiz_state(device))
        else None
    )


NUMBERS: tuple[WizNumberEntityDescription, ...] = (
    WizNumberEntityDescription(
        key="effect_speed",
        translation_key="effect_speed",
        native_min_value=10,
        native_max_value=200,
        native_step=1,
        value_fn=_get_speed,
        set_value_fn=_async_set_speed,
        required_feature="effect",
        entity_category=EntityCategory.CONFIG,
    ),
    WizNumberEntityDescription(
        key="dual_head_ratio",
        translation_key="dual_head_ratio",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        value_fn=_get_ratio,
        set_value_fn=_async_set_ratio,
        required_feature="dual_head",
        # Some ratio-based dual-head lights do not advertise this feature.
        supported_fn=lambda device: _get_ratio(device) is not None,
        entity_category=EntityCategory.CONFIG,
    ),
)


def _supports_number_description(
    device: wizlight, description: WizNumberEntityDescription
) -> bool:
    """Return whether the device supports a number description.

    A runtime support check takes precedence over the advertised feature. Zoned
    dual-head devices advertise the dual-head feature but do not support a
    configurable ratio.
    """
    if description.supported_fn is not None:
        return description.supported_fn(device)
    return getattr(device.bulbtype.features, description.required_feature, False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the wiz speed number."""
    async_add_entities(
        WizSpeedNumber(entry.runtime_data, entry.title, description)
        for description in NUMBERS
        if _supports_number_description(entry.runtime_data.bulb, description)
    )


class WizSpeedNumber(WizEntity, NumberEntity):
    """Defines a WiZ speed number."""

    entity_description: WizNumberEntityDescription
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, wiz_data: WizData, name: str, description: WizNumberEntityDescription
    ) -> None:
        """Initialize an WiZ device."""
        super().__init__(wiz_data, name)
        self.entity_description = description
        self._attr_unique_id = f"{self._device.mac}_{description.key}"
        self._async_update_attrs()

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.entity_description.value_fn(self._device) is not None
        )

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        if (value := self.entity_description.value_fn(self._device)) is not None:
            self._attr_native_value = float(value)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the speed value."""
        await self.entity_description.set_value_fn(self._device, int(value))
        await self.coordinator.async_request_refresh()
