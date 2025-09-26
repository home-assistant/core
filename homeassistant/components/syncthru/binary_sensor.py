"""Support for Samsung Printers with SyncThru web interface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pysyncthru import SyncThru, SyncthruState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SyncThruConfigEntry
from .entity import SyncthruEntity

SYNCTHRU_STATE_PROBLEM = {
    SyncthruState.INVALID: True,
    SyncthruState.OFFLINE: None,
    SyncthruState.NORMAL: False,
    SyncthruState.UNKNOWN: True,
    SyncthruState.WARNING: True,
    SyncthruState.TESTING: False,
    SyncthruState.ERROR: True,
}


@dataclass(frozen=True, kw_only=True)
class SyncThruBinarySensorDescription(BinarySensorEntityDescription):
    """Describes Syncthru binary sensor entities."""

    value_fn: Callable[[SyncThru], bool | None]


BINARY_SENSORS: tuple[SyncThruBinarySensorDescription, ...] = (
    SyncThruBinarySensorDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda printer: printer.is_online(),
    ),
    SyncThruBinarySensorDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda printer: SYNCTHRU_STATE_PROBLEM[printer.device_status()],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SyncThruConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up from config entry."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        SyncThruBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class SyncThruBinarySensor(SyncthruEntity, BinarySensorEntity):
    """Implementation of an abstract Samsung Printer binary sensor platform."""

    entity_description: SyncThruBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
