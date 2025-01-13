"""Number entity platform for Tailwind."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from gotailwind import Tailwind, TailwindDeviceStatus, TailwindError

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TailwindConfigEntry
from .entity import TailwindEntity


@dataclass(frozen=True, kw_only=True)
class TailwindNumberEntityDescription(NumberEntityDescription):
    """Class describing Tailwind number entities."""

    value_fn: Callable[[TailwindDeviceStatus], int]
    set_value_fn: Callable[[Tailwind, float], Awaitable[Any]]


DESCRIPTIONS = [
    TailwindNumberEntityDescription(
        key="brightness",
        translation_key="brightness",
        entity_category=EntityCategory.CONFIG,
        native_step=1,
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.led_brightness,
        set_value_fn=lambda tailwind, brightness: tailwind.status_led(
            brightness=int(brightness),
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TailwindConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tailwind number based on a config entry."""
    async_add_entities(
        TailwindNumberEntity(
            entry.runtime_data,
            description,
        )
        for description in DESCRIPTIONS
    )


class TailwindNumberEntity(TailwindEntity, NumberEntity):
    """Representation of a Tailwind number entity."""

    entity_description: TailwindNumberEntityDescription

    @property
    def native_value(self) -> int | None:
        """Return the number value."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        try:
            await self.entity_description.set_value_fn(self.coordinator.tailwind, value)
        except TailwindError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from exc
        await self.coordinator.async_request_refresh()
