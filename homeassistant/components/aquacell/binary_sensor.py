"""Binary sensors exposing properties of the softener device."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from aioaquacell import Softener

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import AquacellCoordinator
from .entity import AquacellEntity


@dataclass(frozen=True, kw_only=True)
class SoftenerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Softener binary sensor entity."""

    value_fn: Callable[[Softener], StateType]


SENSORS: tuple[SoftenerBinarySensorEntityDescription, ...] = (
    SoftenerBinarySensorEntityDescription(
        key="lid_in_place",
        translation_key="lid_in_place",
        value_fn=lambda softener: cast(bool, softener.lidInPlace),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""

    for softener in config_entry.runtime_data.data:
        async_add_entities(
            AquacellBinarySensor(config_entry.runtime_data, sensor, softener)
            for sensor in SENSORS
        )


class AquacellBinarySensor(AquacellEntity, BinarySensorEntity):
    """Softener binary sensor."""

    entity_description: SoftenerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AquacellCoordinator,
        description: SoftenerBinarySensorEntityDescription,
        softener: Softener,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, softener, description)

        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return cast(bool, self.entity_description.value_fn(self.softener))
