"""Binary sensor platform for Renson WAVES."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import RensonWavesConfigEntry
from .coordinator import RensonWavesData
from .entity import RensonWavesEntity


@dataclass(frozen=True)
class RensonWavesBinarySensorDescription(BinarySensorEntityDescription):
    """Description of a Renson WAVES binary sensor."""

    value_fn: Callable[[RensonWavesData], StateType] = None


BINARY_SENSORS: tuple[RensonWavesBinarySensorDescription, ...] = (
    RensonWavesBinarySensorDescription(
        key="wifi_connected",
        translation_key="wifi_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: (
            data.wifi_status.get("global", {}).get("connection_status", {}).get("value")
            == "connected"
        ),
    ),
    RensonWavesBinarySensorDescription(
        key="room_boost_enabled",
        translation_key="room_boost_enabled",
        value_fn=lambda data: (
            data.decision_room.get("global", {}).get("decision", {}).get("value")
            == "yes"
        ),
    ),
    RensonWavesBinarySensorDescription(
        key="silent_mode_enabled",
        translation_key="silent_mode_enabled",
        value_fn=lambda data: (
            data.decision_silent.get("global", {}).get("decision", {}).get("value")
            == "yes"
        ),
    ),
    RensonWavesBinarySensorDescription(
        key="breeze_mode_enabled",
        translation_key="breeze_mode_enabled",
        value_fn=lambda data: (
            data.decision_breeze.get("global", {}).get("decision", {}).get("value")
            == "yes"
        ),
    ),
)


class RensonWavesBinarySensor(RensonWavesEntity, BinarySensorEntity):
    """Binary sensor for Renson WAVES."""

    entity_description: RensonWavesBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Return True if binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RensonWavesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data

    # Get serial from constellation data
    constellation = coordinator.data.constellation
    serial = constellation.get("global", {}).get("serial", {}).get("value")
    if not serial:
        serial = f"{coordinator.client.host}:{coordinator.client.port}"

    entities: list[BinarySensorEntity] = []

    # Add binary sensors
    for description in BINARY_SENSORS:
        entities.append(
            RensonWavesBinarySensor(
                coordinator=coordinator,
                description=description,
                serial=serial,
            )
        )

    async_add_entities(entities)
