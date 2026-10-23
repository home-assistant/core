"""Support for the Electra binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from electrasmart.device import ElectraAirConditioner

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectraSmartConfigEntry, ElectraSmartCoordinator
from .entity import ElectraEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


def _is_sensor_fault(device: ElectraAirConditioner, field: str) -> bool:
    """Return whether the AC reports one of its temperature sensors as faulty.

    The healthy value of these flags is not identical across models ('NORM'
    and 'NORMAL' are both in the wild) and a unit that does not report the
    field at all is not reporting a fault.
    """
    value = device.measurements.get(field)
    if value is None:
        return False
    return not str(value).upper().startswith("NORM")


@dataclass(frozen=True, kw_only=True)
class ElectraBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe an Electra binary sensor."""

    value_fn: Callable[[ElectraAirConditioner], bool]
    measurement_field: str | None = None


BINARY_SENSORS: tuple[ElectraBinarySensorEntityDescription, ...] = (
    ElectraBinarySensorEntityDescription(
        key="filter_clean_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: device.get_filter_clean_required(),
    ),
    ElectraBinarySensorEntityDescription(
        key="indoor_coil_sensor_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        measurement_field="I_BAD_ICT",
        value_fn=lambda device: _is_sensor_fault(device, "I_BAD_ICT"),
    ),
    ElectraBinarySensorEntityDescription(
        key="return_air_sensor_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        measurement_field="I_BAD_RAT",
        value_fn=lambda device: _is_sensor_fault(device, "I_BAD_RAT"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectraSmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the binary sensors of every AC on the account."""
    coordinator = entry.runtime_data

    async_add_entities(
        ElectraBinarySensorEntity(coordinator, device, description)
        for device in coordinator.api.devices
        for description in BINARY_SENSORS
        # An AC reports a subset of the telemetry, so only expose the binary
        # sensors for the measurements it actually sends.
        if description.measurement_field is None
        or description.measurement_field in device.measurements
    )


class ElectraBinarySensorEntity(ElectraEntity, BinarySensorEntity):
    """Define an Electra binary sensor."""

    entity_description: ElectraBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ElectraSmartCoordinator,
        device: ElectraAirConditioner,
        description: ElectraBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{device.mac}_{description.key}"

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the AC reports the condition."""
        return self.entity_description.value_fn(self._device)
