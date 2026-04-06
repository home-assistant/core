"""Binary sensor platform for NRGkick."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NRGkickConfigEntry, NRGkickData, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity, get_nested_dict_value

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NRGkickBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing NRGkick binary sensor entities."""

    is_on_fn: Callable[[NRGkickData], bool | None]


BINARY_SENSORS: tuple[NRGkickBinarySensorEntityDescription, ...] = (
    NRGkickBinarySensorEntityDescription(
        key="charge_permitted",
        translation_key="charge_permitted",
        is_on_fn=lambda data: (
            bool(value)
            if (
                value := get_nested_dict_value(
                    data.values, "general", "charge_permitted"
                )
            )
            is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick binary sensors based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        NRGkickBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class NRGkickBinarySensor(NRGkickEntity, BinarySensorEntity):
    """Representation of a NRGkick binary sensor."""

    entity_description: NRGkickBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NRGkickDataUpdateCoordinator,
        entity_description: NRGkickBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(self.coordinator.data)
