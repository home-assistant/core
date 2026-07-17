"""Sensor platform for the Nespresso Vertuo integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from nespresso_ble import VMiniDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import NespressoBLEConfigEntry, NespressoBLECoordinator
from .entity import NespressoBLEEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NespressoBLESensorEntityDescription(SensorEntityDescription):
    """Describes a Nespresso Vertuo sensor entity."""

    value_fn: Callable[[VMiniDevice], StateType]


SENSORS: tuple[NespressoBLESensorEntityDescription, ...] = (
    NespressoBLESensorEntityDescription(
        key="machine_status",
        translation_key="machine_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "ready",
            "brewing",
            "heating",
            "descaling",
            "standby",
            "error",
        ],
        value_fn=lambda device: _as_str(device.sensors.get("machineStatus")),
    ),
    NespressoBLESensorEntityDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: _as_str(device.sensors.get("errorCode")),
    ),
    NespressoBLESensorEntityDescription(
        key="water_hardness",
        translation_key="water_hardness",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: _as_int(device.sensors.get("waterHardness")),
    ),
)


def _as_str(value: str | int | bool | None) -> str | None:
    """Return a lowercased string value or None."""
    if value is None:
        return None
    return str(value).lower().replace(" ", "_")


def _as_int(value: str | int | bool | None) -> int | None:
    """Return an int value or None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NespressoBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nespresso Vertuo sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        NespressoBLESensor(coordinator, description) for description in SENSORS
    )


class NespressoBLESensor(NespressoBLEEntity, SensorEntity):
    """A Nespresso Vertuo sensor."""

    entity_description: NespressoBLESensorEntityDescription

    def __init__(
        self,
        coordinator: NespressoBLECoordinator,
        description: NespressoBLESensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.address}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
