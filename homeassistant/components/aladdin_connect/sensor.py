"""Support for Aladdin Connect Garage Door sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from genie_partner_sdk.client import AladdinConnectClient
from genie_partner_sdk.model import GarageDoor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AladdinConnectConfigEntry, AladdinConnectCoordinator
from .entity import AladdinConnectEntity


@dataclass(frozen=True, kw_only=True)
class AccSensorEntityDescription(SensorEntityDescription):
    """Describes AladdinConnect sensor entity."""

    value_fn: Callable[[AladdinConnectClient, str, int], float | None]


SENSORS: tuple[AccSensorEntityDescription, ...] = (
    AccSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=AladdinConnectClient.get_battery_status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AladdinConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aladdin Connect sensor devices."""
    coordinator = entry.runtime_data

    async_add_entities(
        AladdinConnectSensor(coordinator, door, description)
        for description in SENSORS
        for door in coordinator.doors
    )


class AladdinConnectSensor(AladdinConnectEntity, SensorEntity):
    """A sensor implementation for Aladdin Connect devices."""

    entity_description: AccSensorEntityDescription

    def __init__(
        self,
        coordinator: AladdinConnectCoordinator,
        device: GarageDoor,
        description: AccSensorEntityDescription,
    ) -> None:
        """Initialize a sensor for an Aladdin Connect device."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.unique_id}-{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.acc, self._device.device_id, self._device.door_number
        )
