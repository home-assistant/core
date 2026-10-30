"""Binary sensors for the Spin EV Charger integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from spinev_ble import ChargerStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SpinEvConfigEntry
from .entity import SpinEvEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SpinEvBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Spin EV binary sensor."""

    value_fn: Callable[[ChargerStatus], bool | None]


BINARY_SENSORS: tuple[SpinEvBinarySensorEntityDescription, ...] = (
    SpinEvBinarySensorEntityDescription(
        key="vehicle_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda status: status.state.has_vehicle if status.state else None,
    ),
    SpinEvBinarySensorEntityDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda status: status.has_alarms,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpinEvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the charger binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        SpinEvBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class SpinEvBinarySensor(SpinEvEntity, BinarySensorEntity):
    """A condition read from the charger."""

    entity_description: SpinEvBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True while the condition holds."""
        return self.entity_description.value_fn(self.coordinator.data)
