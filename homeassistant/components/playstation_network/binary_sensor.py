"""Binary Sensor platform for PlayStation Network integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    PlaystationNetworkConfigEntry,
    PlaystationNetworkData,
    PlaystationNetworkUserDataCoordinator,
)
from .entity import PlaystationNetworkServiceEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class PlaystationNetworkBinarySensorEntityDescription(BinarySensorEntityDescription):
    """PlayStation Network binary sensor description."""

    is_on_fn: Callable[[PlaystationNetworkData], bool]


class PlaystationNetworkBinarySensor(StrEnum):
    """PlayStation Network binary sensors."""

    PS_PLUS_STATUS = "ps_plus_status"


BINARY_SENSOR_DESCRIPTIONS: tuple[
    PlaystationNetworkBinarySensorEntityDescription, ...
] = (
    PlaystationNetworkBinarySensorEntityDescription(
        key=PlaystationNetworkBinarySensor.PS_PLUS_STATUS,
        translation_key=PlaystationNetworkBinarySensor.PS_PLUS_STATUS,
        is_on_fn=lambda psn: psn.profile["isPlus"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PlaystationNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = config_entry.runtime_data.user_data
    async_add_entities(
        PlaystationNetworkBinarySensorEntity(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class PlaystationNetworkBinarySensorEntity(
    PlaystationNetworkServiceEntity,
    BinarySensorEntity,
):
    """Representation of a PlayStation Network binary sensor entity."""

    entity_description: PlaystationNetworkBinarySensorEntityDescription
    coordinator: PlaystationNetworkUserDataCoordinator

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""

        return self.entity_description.is_on_fn(self.coordinator.data)
