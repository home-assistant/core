"""Sensor platform for DayBetter temperature & humidity."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DayBetterConfigEntry, DayBetterRuntimeData
from .coordinator import DayBetterCoordinator

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class DayBetterSensorEntityDescription(SensorEntityDescription):
    """Describes a DayBetter sensor."""

    exists_fn: Callable[[dict[str, Any]], bool]
    value_fn: Callable[[dict[str, Any]], float | int | None]


def _safe_div(value: Any, divisor: float) -> float | None:
    """Divide a raw value if possible."""
    if value is None:
        return None
    try:
        return int(value) / divisor
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    """Cast a value to int if possible."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


DESCRIPTIONS: tuple[DayBetterSensorEntityDescription, ...] = (
    DayBetterSensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        exists_fn=lambda device: device.get("temp") is not None,
        value_fn=lambda device: _safe_div(device.get("temp"), 10),
    ),
    DayBetterSensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        exists_fn=lambda device: device.get("humi") is not None,
        value_fn=lambda device: _safe_div(device.get("humi"), 10),
    ),
    DayBetterSensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        exists_fn=lambda device: device.get("battery") is not None,
        value_fn=lambda device: _safe_int(device.get("battery")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DayBetterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up DayBetter sensors from a config entry."""
    runtime_data: DayBetterRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    devices = coordinator.data or []

    entities: list[SensorEntity] = []
    for device in devices:
        device_id_raw = device.get("deviceId")
        if device_id_raw is None:
            continue
        device_id = str(device_id_raw)

        for description in DESCRIPTIONS:
            if not description.exists_fn(device):
                continue

            entities.append(
                DayBetterSensor(
                    coordinator=coordinator,
                    device=device,
                    device_id=device_id,
                    description=description,
                )
            )

    async_add_entities(entities)


class DayBetterSensor(CoordinatorEntity[DayBetterCoordinator], SensorEntity):
    """DayBetter sensor built from an entity description."""

    entity_description: DayBetterSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DayBetterCoordinator,
        device: dict[str, Any],
        device_id: str,
        description: DayBetterSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device = device
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_translation_key = description.key
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.get("deviceGroupName") or device.get("deviceName", "DayBetter"),
            manufacturer="DayBetter",
            model=device.get("deviceClass", "Sensor"),
        )

    def _get_device(self) -> dict[str, Any] | None:
        """Get current device data from coordinator."""
        data = self.coordinator.data
        if not data:
            return None

        for device in data:
            if (
                device.get("deviceId") == self._device_id
                or str(device.get("deviceId")) == self._device_id
            ):
                return device

        return None

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        device = self._get_device()
        if not device:
            return None

        return self.entity_description.value_fn(device)
