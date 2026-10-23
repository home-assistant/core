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
from homeassistant.core import HomeAssistant, callback
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

    value_fn: Callable[[ElectraAirConditioner], bool | None]
    is_supported: Callable[[ElectraAirConditioner], bool]


BINARY_SENSORS: tuple[ElectraBinarySensorEntityDescription, ...] = (
    ElectraBinarySensorEntityDescription(
        key="filter_clean_required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        # The reminder lives in the operation state, not in the diagnostics, so
        # the entity is only created for a unit that reports the field: a unit
        # that omits it would otherwise show a reminder it never sent.
        is_supported=lambda device: device.get_filter_clean_required() is not None,
        value_fn=lambda device: device.get_filter_clean_required(),
    ),
    ElectraBinarySensorEntityDescription(
        key="indoor_coil_sensor_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_supported=lambda device: "I_BAD_ICT" in device.measurements,
        value_fn=lambda device: _is_sensor_fault(device, "I_BAD_ICT"),
    ),
    ElectraBinarySensorEntityDescription(
        key="return_air_sensor_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_supported=lambda device: "I_BAD_RAT" in device.measurements,
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
    added: set[tuple[str, str]] = set()

    @callback
    def _add_missing_binary_sensors() -> None:
        """Add a binary sensor for every flag an AC reports.

        An AC reports a subset of the telemetry, and one that was offline when
        the integration set up reports nothing at all, so the flags are
        re-read on every update instead of only at setup.
        """
        entities: list[ElectraBinarySensorEntity] = []
        for device in coordinator.api.devices:
            for description in BINARY_SENSORS:
                if (device.mac, description.key) in added or not (
                    description.is_supported(device)
                ):
                    continue
                added.add((device.mac, description.key))
                entities.append(
                    ElectraBinarySensorEntity(coordinator, device, description)
                )

        if entities:
            async_add_entities(entities)

    _add_missing_binary_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_missing_binary_sensors))


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
    def is_on(self) -> bool | None:
        """Return whether the AC reports the condition, or None if it does not."""
        return self.entity_description.value_fn(self._device)
