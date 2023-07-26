"""Support for Rituals Perfume Genie numbers."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pyrituals import Diffuser

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsDataUpdateCoordinator
from .entity import DiffuserEntity


@dataclass
class RitualsNumberEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Diffuser], int]
    set_value_fn: Callable[[Diffuser, int], Awaitable[Any]]


@dataclass
class RitualsNumberEntityDescription(
    NumberEntityDescription, RitualsNumberEntityDescriptionMixin
):
    """Class describing Rituals number entities."""


ENTITY_DESCRIPTIONS = (
    RitualsNumberEntityDescription(
        key="perfume_amount",
        translation_key="perfume_amount",
        icon="mdi:gauge",
        native_min_value=1,
        native_max_value=3,
        value_fn=lambda diffuser: diffuser.perfume_amount,
        set_value_fn=lambda diffuser, value: diffuser.set_perfume_amount(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the diffuser numbers."""
    coordinators: dict[str, RitualsDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        RitualsNumberEntity(coordinator, description)
        for coordinator in coordinators.values()
        for description in ENTITY_DESCRIPTIONS
    )


class RitualsNumberEntity(DiffuserEntity, NumberEntity):
    """Representation of a diffuser number entity."""

    entity_description: RitualsNumberEntityDescription

    @property
    def native_value(self) -> int:
        """Return the number value."""
        return self.entity_description.value_fn(self.coordinator.diffuser)

    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        if not value.is_integer():
            raise ValueError(f"Can't set value to {value}. Value must be an integer.")
        await self.entity_description.set_value_fn(
            self.coordinator.diffuser, int(value)
        )
