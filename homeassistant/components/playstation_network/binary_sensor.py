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

from .const import ASSETS_PATH
from .coordinator import PlaystationNetworkConfigEntry, PlaystationNetworkData
from .entity import PlaystationNetworkServiceEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class PlaystationNetworkBinarySensorEntityDescription(BinarySensorEntityDescription):
    """PlayStation Network binary sensor description."""

    is_on_fn: Callable[[PlaystationNetworkData], bool]
    entity_picture: str | None = None


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
        entity_picture=f"{ASSETS_PATH}/psplus.png",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PlaystationNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = config_entry.runtime_data
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

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""

        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""

        return self.entity_description.entity_picture or super().entity_picture
