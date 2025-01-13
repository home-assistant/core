"""Binary sensor platform for IronOS integration."""

from __future__ import annotations

from enum import StrEnum

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IronOSConfigEntry
from .coordinator import IronOSLiveDataCoordinator
from .entity import IronOSBaseEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class PinecilBinarySensor(StrEnum):
    """Pinecil Binary Sensors."""

    TIP_CONNECTED = "tip_connected"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IronOSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    coordinator = entry.runtime_data.live_data

    entity_description = BinarySensorEntityDescription(
        key=PinecilBinarySensor.TIP_CONNECTED,
        translation_key=PinecilBinarySensor.TIP_CONNECTED,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    )

    async_add_entities([IronOSBinarySensorEntity(coordinator, entity_description)])


class IronOSBinarySensorEntity(IronOSBaseEntity, BinarySensorEntity):
    """Representation of a IronOS binary sensor entity."""

    coordinator: IronOSLiveDataCoordinator

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.has_tip
