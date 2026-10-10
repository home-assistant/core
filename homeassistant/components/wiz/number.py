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
from .entity import WizEntity


@dataclass(frozen=True, kw_only=True)
class WizNumberEntityDescription(NumberEntityDescription):
    """Class to describe a WiZ number entity."""

    required_feature: str
    set_value_fn: Callable[[wizlight, int], Coroutine[None, None, None]]
    value_fn: Callable[[wizlight], int | None]
    # Optional fallback, checked against runtime state when required_feature is
    # not advertised by the bulb type.
    supported_fn: Callable[[wizlight], bool] | None = None


async def _async_set_speed(device: wizlight, speed: int) -> None:
    await device.set_speed(speed)


async def _async_set_ratio(device: wizlight, ratio: int) -> None:
    await device.set_ratio(ratio)


NUMBERS: tuple[WizNumberEntityDescription, ...] = (
    WizNumberEntityDescription(
        key="effect_speed",
        translation_key="effect_speed",
        native_min_value=10,
        native_max_value=200,
        native_step=1,
        value_fn=lambda device: cast(int | None, device.state.get_speed()),
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
        value_fn=lambda device: cast(int | None, device.state.get_ratio()),
        set_value_fn=_async_set_ratio,
        required_feature="dual_head",
        # Some ratio-based dual-head lights do not advertise this feature.
        supported_fn=lambda device: (
            device.state is not None and device.state.get_ratio() is not None
        ),
        entity_category=EntityCategory.CONFIG,
    ),
)


def _supports_number_description(
    device: wizlight, description: WizNumberEntityDescription
) -> bool:
    """Return whether the device supports a number description.

    When the bulb type does not advertise the required feature, ``supported_fn``
    is evaluated as a fallback. It inspects the current runtime state (e.g.
    whether a ratio is present), so the result depends on the device state at
    call time.
    """
    return getattr(device.bulbtype.features, description.required_feature, False) or (
        description.supported_fn is not None and description.supported_fn(device)
    )


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
