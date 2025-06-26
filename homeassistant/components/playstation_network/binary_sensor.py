"""Binary Sensor platform for PlayStation Network integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    PlaystationNetworkConfigEntry,
    PlaystationNetworkCoordinator,
    PlaystationNetworkData,
)

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class PlaystationNetworkBinarySensorEntityDescription(BinarySensorEntityDescription):
    """PlayStation Network sensor description."""

    value_fn: Callable[[PlaystationNetworkData], StateType]


class PlaystationNetworkBinarySensor(StrEnum):
    """PlayStation Network sensors."""

    ONLINE_STATUS = "online_status"
    PS_PLUS_STATUS = "ps_plus_status"


BINARY_SENSOR_DESCRIPTIONS: tuple[
    PlaystationNetworkBinarySensorEntityDescription, ...
] = (
    PlaystationNetworkBinarySensorEntityDescription(
        key=PlaystationNetworkBinarySensor.ONLINE_STATUS,
        translation_key=PlaystationNetworkBinarySensor.ONLINE_STATUS,
        name="Online",
        value_fn=(lambda psn: psn.available),
    ),
    PlaystationNetworkBinarySensorEntityDescription(
        key=PlaystationNetworkBinarySensor.PS_PLUS_STATUS,
        translation_key=PlaystationNetworkBinarySensor.PS_PLUS_STATUS,
        name="PlayStation Plus",
        value_fn=(lambda psn: psn.profile["isPlus"]),
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
    CoordinatorEntity[PlaystationNetworkCoordinator], BinarySensorEntity
):
    """Representation of a PlayStation Network sensor entity."""

    entity_description: PlaystationNetworkBinarySensorEntityDescription
    coordinator: PlaystationNetworkCoordinator

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlaystationNetworkCoordinator,
        description: PlaystationNetworkBinarySensorEntityDescription,
    ) -> None:
        """Initialize a binary sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"
        self._attr_translation_key = description.translation_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            name=coordinator.data.username,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Sony Interactive Entertainment",
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""

        return bool(self.entity_description.value_fn(self.coordinator.data))
