"""Support for Lektrico number entities."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from lektricowifi import Device

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import (
    ATTR_SERIAL_NUMBER,
    CONF_TYPE,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LektricoConfigEntry, LektricoDeviceDataUpdateCoordinator
from .entity import LektricoEntity


@dataclass(frozen=True, kw_only=True)
class LektricoNumberEntityDescription(NumberEntityDescription):
    """Describes Lektrico number entity."""

    value_fn: Callable[[dict[str, Any]], int]
    set_value_fn: Callable[[Device, int], Coroutine[Any, Any, dict[Any, Any]]]


NUMBERS: tuple[LektricoNumberEntityDescription, ...] = (
    LektricoNumberEntityDescription(
        key="led_max_brightness",
        translation_key="led_max_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: int(data["led_max_brightness"]),
        set_value_fn=lambda data, value: data.set_led_max_brightness(value),
    ),
    LektricoNumberEntityDescription(
        key="dynamic_limit",
        translation_key="dynamic_limit",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=32,
        native_step=1,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_fn=lambda data: int(data["dynamic_current"]),
        set_value_fn=lambda data, value: data.set_dynamic_current(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LektricoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lektrico number entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        LektricoNumber(
            description,
            coordinator,
            f"{entry.data[CONF_TYPE]}_{entry.data[ATTR_SERIAL_NUMBER]}",
        )
        for description in NUMBERS
    )


class LektricoNumber(LektricoEntity, NumberEntity):
    """Defines a Lektrico number entity."""

    entity_description: LektricoNumberEntityDescription

    def __init__(
        self,
        description: LektricoNumberEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize Lektrico number."""
        super().__init__(coordinator, device_name)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the number."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Set the selected value."""
        await self.entity_description.set_value_fn(self.coordinator.device, int(value))
        await self.coordinator.async_request_refresh()
