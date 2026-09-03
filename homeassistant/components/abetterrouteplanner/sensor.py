"""Sensor platform for the A Better Routeplanner integration.

Which metrics a vehicle reports varies by make, model and connectivity, so its
sensor set cannot be known up front — it is only learned from what the vehicle
actually sends. Entities are therefore created lazily, on a metric's first
value. A vehicle that has reported before but is parked now shows up as an
unavailable registry entry until it next wakes.

The ``charging_state`` option strings are HA-owned rather than derived from the
library enum, so a library-side value change cannot alter a reported state.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from aioabrp import ChargingState, Metric, MetricValue, Telemetry

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfEnergyDistance,
    UnitOfLength,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AbetterrouteplannerConfigEntry, AbrpTelemetryCoordinator

PARALLEL_UPDATES = 0


CHARGING_STATE_OPTIONS: dict[ChargingState, str] = {
    ChargingState.CHARGING_AC: "charging_ac",
    ChargingState.CHARGING_DC: "charging_dc",
    ChargingState.CHARGING_UNKNOWN: "charging_unknown",
    ChargingState.NOT_CHARGING: "not_charging",
    ChargingState.PLUGGED_IN: "plugged_in",
}


@dataclass(frozen=True, kw_only=True)
class AbrpTelemetrySensorEntityDescription[T](SensorEntityDescription):
    """SensorEntityDescription binding a sensor to its telemetry ``Metric``.

    ``key`` is HA-owned rather than derived from ``Metric.value`` so unique_ids
    survive a library-side enum change.
    """

    metric: Metric
    value_fn: Callable[[Telemetry], MetricValue[T] | None]


@dataclass(frozen=True, kw_only=True)
class AbrpNumericSensorEntityDescription(AbrpTelemetrySensorEntityDescription[float]):
    """Description for a numeric telemetry sensor (soc / power / voltage / ...)."""


@dataclass(frozen=True, kw_only=True)
class AbrpEnumSensorEntityDescription(AbrpTelemetrySensorEntityDescription[str]):
    """Description for the categorical ENUM telemetry sensor (charging_state).

    The ``unused-ignore`` below is needed because the narrowed ``value_fn``
    assignment error only appears in a partial mypy run.
    """

    value_fn: Callable[[Telemetry], MetricValue[ChargingState] | None]  # type: ignore[assignment, unused-ignore]


SENSORS: tuple[
    AbrpNumericSensorEntityDescription | AbrpEnumSensorEntityDescription, ...
] = (
    AbrpNumericSensorEntityDescription(
        key="soc",
        translation_key="soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        metric=Metric.SOC,
        value_fn=lambda t: t.soc,
    ),
    AbrpNumericSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        metric=Metric.POWER,
        value_fn=lambda t: t.power,
    ),
    AbrpNumericSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        metric=Metric.VOLTAGE,
        value_fn=lambda t: t.voltage,
    ),
    AbrpNumericSensorEntityDescription(
        key="soe",
        translation_key="soe",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        metric=Metric.SOE,
        value_fn=lambda t: t.soe,
    ),
    AbrpNumericSensorEntityDescription(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=0,
        metric=Metric.ODOMETER,
        value_fn=lambda t: t.odometer,
    ),
    AbrpNumericSensorEntityDescription(
        key="calibrated_ref_cons",
        translation_key="calibrated_ref_cons",
        device_class=SensorDeviceClass.ENERGY_DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergyDistance.WATT_HOUR_PER_KM,
        # HA defaults this device class to 0 decimals, rendering 5.71 km/kWh as "6".
        suggested_display_precision=1,
        metric=Metric.CALIBRATED_REF_CONS,
        value_fn=lambda t: t.calibrated_ref_cons,
    ),
    AbrpNumericSensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        # No ``state_class``: capacity is a fixed spec figure that only moves on
        # an occasional recalibration, so long-term statistics would record a
        # flat series. ``TOTAL`` is not an alternative: ENERGY_STORAGE permits
        # only ``MEASUREMENT``.
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        metric=Metric.BATTERY_CAPACITY,
        value_fn=lambda t: t.battery_capacity,
    ),
    AbrpNumericSensorEntityDescription(
        key="soh",
        translation_key="soh",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        metric=Metric.SOH,
        value_fn=lambda t: t.soh,
    ),
    AbrpNumericSensorEntityDescription(
        key="range",
        translation_key="range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        # ``MEASUREMENT``, not ``TOTAL_INCREASING``: rises on charge, falls on drive.
        suggested_display_precision=0,
        metric=Metric.RANGE,
        value_fn=lambda t: t.range,
    ),
    AbrpNumericSensorEntityDescription(
        key="battery_temperature",
        translation_key="battery_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        metric=Metric.BATTERY_TEMPERATURE,
        value_fn=lambda t: t.battery_temperature,
    ),
    AbrpEnumSensorEntityDescription(
        key="charging_state",
        translation_key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(CHARGING_STATE_OPTIONS.values()),
        metric=Metric.CHARGING_STATE,
        value_fn=lambda t: t.charging_state,
    ),
)


def _telemetry_unique_id(
    entry: AbetterrouteplannerConfigEntry, vehicle_id: int, key: str
) -> str:
    """Build a telemetry sensor's ``unique_id`` — the one definition of the scheme."""
    return f"{entry.unique_id}_{vehicle_id}_{key}"


def _extract_value(
    description: AbrpNumericSensorEntityDescription | AbrpEnumSensorEntityDescription,
    metric_value: MetricValue,
) -> float | str | None:
    """Extract a description's display value from a MetricValue (presence probe)."""
    value = metric_value.value
    if isinstance(description, AbrpEnumSensorEntityDescription):
        return (
            CHARGING_STATE_OPTIONS.get(value)
            if isinstance(value, ChargingState)
            else None
        )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _build_telemetry_sensor(
    coordinator: AbrpTelemetryCoordinator,
    entry: AbetterrouteplannerConfigEntry,
    vehicle_id: int,
    description: AbrpNumericSensorEntityDescription | AbrpEnumSensorEntityDescription,
) -> AbrpTelemetrySensor[float] | AbrpTelemetrySensor[str]:
    """Dispatch on the description type to the matching concrete sensor."""
    if isinstance(description, AbrpEnumSensorEntityDescription):
        return AbrpEnumSensor(coordinator, entry, vehicle_id, description)
    return AbrpNumericSensor(coordinator, entry, vehicle_id, description)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbetterrouteplannerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create telemetry sensors for every vehicle in the ABRP garage."""
    runtime = entry.runtime_data
    vehicles = runtime.vehicles
    telemetry_coordinator = runtime.telemetry_coordinator

    added: set[tuple[int, Metric]] = set()

    @callback
    def _add_new_sensors() -> None:
        """Create a sensor per ``(vehicle, metric)`` pair that now carries a value."""
        entities: list[SensorEntity] = []
        for raw, _ in vehicles:
            vehicle_id = raw.vehicle_id
            tlm = telemetry_coordinator.data.get(vehicle_id)
            if tlm is None:
                continue
            for description in SENSORS:
                if (vehicle_id, description.metric) in added:
                    continue
                metric_value = description.value_fn(tlm)
                if metric_value is None:
                    continue
                if _extract_value(description, metric_value) is None:
                    continue
                entities.append(
                    _build_telemetry_sensor(
                        telemetry_coordinator, entry, vehicle_id, description
                    )
                )
                added.add((vehicle_id, description.metric))
        async_add_entities(entities)

    entry.async_on_unload(telemetry_coordinator.async_add_listener(_add_new_sensors))
    _add_new_sensors()


class AbrpTelemetrySensor[T: (float, str)](
    CoordinatorEntity[AbrpTelemetryCoordinator], SensorEntity
):
    """One telemetry sensor (soc / power / voltage / charging_state) per vehicle."""

    _attr_has_entity_name = True
    entity_description: AbrpTelemetrySensorEntityDescription[T]

    def __init__(
        self,
        coordinator: AbrpTelemetryCoordinator,
        entry: AbetterrouteplannerConfigEntry,
        vehicle_id: int,
        description: AbrpTelemetrySensorEntityDescription[T],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._vehicle_id = vehicle_id
        self._metric = description.metric
        scope = f"{entry.unique_id}_{vehicle_id}"
        self._attr_unique_id = _telemetry_unique_id(entry, vehicle_id, description.key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, scope)},
        )

    def _value_from_metric(self, metric_value: MetricValue) -> T | None:
        """Coerce a live ``MetricValue`` to this sensor's display ``T``."""
        raise NotImplementedError

    @property
    @override
    def native_value(self) -> StateType:
        """Return this metric's latest reading.

        Annotated ``StateType``, not ``T | None``: HA's ``home-assistant-return-type``
        pylint plugin checks the literal annotation and won't resolve the TypeVar.
        """
        tlm = self.coordinator.data.get(self._vehicle_id)
        if tlm is None:
            return None
        metric_value = self.entity_description.value_fn(tlm)
        if metric_value is None:
            return None
        return self._value_from_metric(metric_value)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the reading's wire time and upstream provider."""
        attrs: dict[str, Any] = {}
        stamp = self.coordinator.last_reported_at.get(self._vehicle_id, {}).get(
            self._metric
        )
        if stamp is not None:
            attrs["last_reported_at"] = stamp
        provider = self.coordinator.last_provider.get(self._vehicle_id, {}).get(
            self._metric
        )
        if provider is not None:
            attrs["provider"] = provider
        return attrs or None

    @property
    @override
    def available(self) -> bool:
        """Return True whenever a value is surfacing.

        Decoupled from ``CoordinatorEntity.available``: ABRP goes silent between
        vehicle wakes, which is steady state rather than a failure. A terminal
        stream auth failure is the exception — nothing will refresh the value,
        so it stops being reported rather than going stale indefinitely.
        """
        return not self.coordinator.stream_auth_failed and self.native_value is not None


class AbrpNumericSensor(AbrpTelemetrySensor[float]):
    """A numeric telemetry sensor (soc / power / voltage / ...)."""

    entity_description: AbrpNumericSensorEntityDescription

    @override
    def _value_from_metric(self, metric_value: MetricValue) -> float | None:
        """Return the numeric reading; ignore a non-float value defensively."""
        value = metric_value.value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None


class AbrpEnumSensor(AbrpTelemetrySensor[str]):
    """The categorical ENUM telemetry sensor (charging_state)."""

    entity_description: AbrpEnumSensorEntityDescription

    @override
    def _value_from_metric(self, metric_value: MetricValue) -> str | None:
        """Map the library ``ChargingState`` to this integration's option string."""
        value = metric_value.value
        if isinstance(value, ChargingState):
            return CHARGING_STATE_OPTIONS.get(value)
        return None
