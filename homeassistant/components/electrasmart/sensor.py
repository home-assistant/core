"""Support for the Electra sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from electrasmart.device import ElectraAirConditioner

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElectraSmartConfigEntry, ElectraSmartCoordinator
from .entity import ElectraEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


def _as_int(device: ElectraAirConditioner, field: str) -> int | None:
    """Return a numeric measurement, or None for a value that is not a number."""
    try:
        return int(device.measurements[field])
    except KeyError, TypeError, ValueError:
        return None


@dataclass(frozen=True, kw_only=True)
class ElectraSensorEntityDescription(SensorEntityDescription):
    """Describe an Electra sensor."""

    measurement_field: str
    value_fn: Callable[[ElectraAirConditioner], float | int | None]


SENSORS: tuple[ElectraSensorEntityDescription, ...] = (
    ElectraSensorEntityDescription(
        key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        measurement_field="WI_FI_RSSI",
        value_fn=lambda device: _as_int(device, "WI_FI_RSSI"),
    ),
    ElectraSensorEntityDescription(
        key="indoor_coil_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        measurement_field="I_ICT",
        value_fn=lambda device: device.get_measurement_temperature("I_ICT"),
    ),
    ElectraSensorEntityDescription(
        key="outdoor_coil_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        measurement_field="O_OCT",
        value_fn=lambda device: device.get_measurement_temperature("O_OCT"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElectraSmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors of every AC on the account."""
    coordinator = entry.runtime_data
    added: set[tuple[str, str]] = set()

    @callback
    def _add_missing_sensors() -> None:
        """Add a sensor for every measurement an AC reports.

        An AC reports a subset of the telemetry, and one that was offline when
        the integration set up reports nothing at all, so the fields are
        re-read on every update instead of only at setup.
        """
        entities: list[ElectraSensorEntity] = []
        for device in coordinator.api.devices:
            for description in SENSORS:
                if (
                    device.mac,
                    description.key,
                ) in added or description.measurement_field not in device.measurements:
                    continue
                added.add((device.mac, description.key))
                entities.append(ElectraSensorEntity(coordinator, device, description))

        if entities:
            async_add_entities(entities)

    _add_missing_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_missing_sensors))


class ElectraSensorEntity(ElectraEntity, SensorEntity):
    """Define an Electra sensor."""

    entity_description: ElectraSensorEntityDescription

    def __init__(
        self,
        coordinator: ElectraSmartCoordinator,
        device: ElectraAirConditioner,
        description: ElectraSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{device.mac}_{description.key}"

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the value of the measurement."""
        return self.entity_description.value_fn(self._device)
