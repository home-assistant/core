"""Binary sensor entities for the madVR integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MadVRConfigEntry
from .coordinator import MadVRCoordinator
from .entity import MadVREntity

_HDR_FLAG = "hdr_flag"
_OUTGOING_HDR_FLAG = "outgoing_hdr_flag"
_POWER_STATE = "power_state"
_SIGNAL_STATE = "signal_state"


@dataclass(frozen=True, kw_only=True)
class MadvrBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe madVR binary sensor entity."""

    value_fn: Callable[[MadVRCoordinator], bool]


BINARY_SENSORS: tuple[MadvrBinarySensorEntityDescription, ...] = (
    MadvrBinarySensorEntityDescription(
        key=_POWER_STATE,
        translation_key=_POWER_STATE,
        value_fn=lambda coordinator: coordinator.data.get("is_on", False),
    ),
    MadvrBinarySensorEntityDescription(
        key=_SIGNAL_STATE,
        translation_key=_SIGNAL_STATE,
        value_fn=lambda coordinator: coordinator.data.get("is_signal", False),
    ),
    MadvrBinarySensorEntityDescription(
        key=_HDR_FLAG,
        translation_key=_HDR_FLAG,
        value_fn=lambda coordinator: coordinator.data.get("hdr_flag", False),
    ),
    MadvrBinarySensorEntityDescription(
        key=_OUTGOING_HDR_FLAG,
        translation_key=_OUTGOING_HDR_FLAG,
        value_fn=lambda coordinator: coordinator.data.get("outgoing_hdr_flag", False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MadVRConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        MadvrBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class MadvrBinarySensor(MadVREntity, BinarySensorEntity):
    """Base class for madVR binary sensors."""

    entity_description: MadvrBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MadVRCoordinator,
        description: MadvrBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.mac}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator)
