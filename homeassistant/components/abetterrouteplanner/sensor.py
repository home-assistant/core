"""Sensor platform for the A Better Routeplanner integration.

Each selected vehicle's device is anchored in
:func:`homeassistant.components.abetterrouteplanner.async_setup_entry`
at setup time. The catalog's display metadata (e.g.
``"Rivian R2 2026 RWD"``) surfaces via :attr:`DeviceInfo.model` on the
device card, composed by :attr:`aioabrp.VehicleModelDisplay.display_name`
from the v2 catalog by the one-shot garage fetch at setup time.

``AbrpTelemetrySensor`` exposes the numeric metrics (soc / power /
voltage / etc.) backed by the SSE telemetry coordinator. Entities are
created lazily: at setup time the platform inspects the coordinator's
seeded snapshot and only creates entities for metrics that
carry a non-None value. Metrics that arrive later are picked up via a
dispatcher signal fired along the push path
``aioabrp.TelemetryStream → AbrpTelemetryCoordinator.on_update``.
"""

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, override

from aioabrp import ChargingState, Metric, MetricValue, Telemetry

from homeassistant.components.sensor import (
    RestoreSensor,
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VEHICLE_IDS, DOMAIN, signal_new_metric
from .coordinator import AbetterrouteplannerConfigEntry, AbrpTelemetryCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


# HA owns the charging_state option strings (the sensor's ``options`` list and
# its translation keys live in this integration, not the library). The map is
# total over ``ChargingState`` so ``native_value`` always resolves to a valid
# option for any member the library emits. Kept HA-side — not derived from
# ``ChargingState.value`` — so a library-side enum-value change cannot silently
# alter this integration's entity state strings or its required translations.
CHARGING_STATE_OPTIONS: dict[ChargingState, str] = {
    ChargingState.CHARGING_AC: "charging_ac",
    ChargingState.CHARGING_DC: "charging_dc",
    ChargingState.CHARGING_UNKNOWN: "charging_unknown",
    ChargingState.NOT_CHARGING: "not_charging",
    ChargingState.PLUGGED_IN: "plugged_in",
}


def _is_clean_provider_str(value: object) -> bool:
    """Return True iff ``value`` is a non-empty, unpadded string.

    Provider enum values are closed and ASCII-only, so the guard rejects
    padded input rather than stripping it — a padded value is an upstream
    wire-shape regression we want surfaced, not silently normalised. Note
    ``str.strip()`` only handles ``isspace()`` whitespace, so ZWS-family
    padding (``U+200B/200C/200D/FEFF``) survives and intentionally mismatches
    the ``Provider`` literal downstream rather than being sanitised here.
    """
    return isinstance(value, str) and bool(value) and value == value.strip()


@dataclass(frozen=True, kw_only=True)
class AbrpTelemetrySensorEntityDescription[T](SensorEntityDescription):
    """SensorEntityDescription binding a sensor to its telemetry ``Metric``.

    Generic over the extracted value type ``T`` (``float`` for the numeric
    metrics, ``str`` for the categorical ENUM metric) so the numeric and
    enum sensors share one machinery without a ``float | str`` union
    leaking into either. The proven PEP 695 precedent for a generic
    ``SensorEntityDescription`` is ``airos/sensor.py``.

    ``key`` is kept explicit (not derived from ``metric.value``) on purpose:
    the ``key`` strings are HA-owned and decoupled from ``Metric.value`` to
    keep unique_ids / entity_ids stable across any library-side enum-value
    change.

    ``value_fn`` extracts the typed ``MetricValue[T]`` from a ``Telemetry``
    struct, returning ``None`` when the metric is absent. It is the single
    access path for ``native_value`` and ``available``, keeping the
    coordinator storage format opaque to the sensor layer.
    """

    metric: Metric
    value_fn: Callable[[Telemetry], MetricValue[T] | None]


@dataclass(frozen=True, kw_only=True)
class AbrpNumericSensorEntityDescription(AbrpTelemetrySensorEntityDescription[float]):
    """Description for a numeric telemetry sensor (soc / power / voltage / ...)."""


@dataclass(frozen=True, kw_only=True)
class AbrpEnumSensorEntityDescription(AbrpTelemetrySensorEntityDescription[str]):
    """Description for the categorical ENUM telemetry sensor (charging_state).

    Overrides ``value_fn`` with a ``ChargingState``-typed variant because the
    raw ``Telemetry`` field returns ``MetricValue[ChargingState]``; the parent's
    ``T=str`` typing covers the coerced HA option string AFTER
    ``_value_from_metric`` maps it.
    """

    value_fn: Callable[[Telemetry], MetricValue[ChargingState] | None]  # type: ignore[assignment]


# Telemetry sensor catalogue. Each description binds a ``Metric`` whose typed
# ``MetricValue`` the coordinator surfaces; the platform only creates an entity
# once that metric first carries a non-None value for a given vehicle. The
# ``key`` strings are intentionally HA-owned and decoupled from ``Metric.value``
# so unique_ids / entity_ids stay stable across a library-side enum change.
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
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        metric=Metric.POWER,
        value_fn=lambda t: t.power,
    ),
    AbrpNumericSensorEntityDescription(
        key="voltage",
        translation_key="voltage",
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
        # HA's default precision for ENERGY_DISTANCE is 0
        # (``sensor/const.py:763`` UNITS_PRECISION key), which would render
        # e.g. 175 Wh/km cleanly but the user-locale-converted 5.71 km/kWh
        # as "6". One decimal place preserves the meaningful precision of
        # the fractional km/kWh display without inflating noise on the
        # native Wh/km surface.
        suggested_display_precision=1,
        metric=Metric.CALIBRATED_REF_CONS,
        value_fn=lambda t: t.calibrated_ref_cons,
    ),
    AbrpNumericSensorEntityDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        # No ``state_class``: capacity is a static nameplate value (and an
        # occasional recalibration jump). Opting out of the LTS pipeline
        # keeps the recorder from emitting per-poll history for a value
        # that effectively never changes. Pinned by
        # ``test_battery_capacity_sensor_lazy_creates_static``.
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        metric=Metric.BATTERY_CAPACITY,
        value_fn=lambda t: t.battery_capacity,
    ),
    AbrpNumericSensorEntityDescription(
        key="soh",
        translation_key="soh",
        # No ``device_class``: ``SensorDeviceClass.BATTERY`` is "percentage
        # of battery that is left" (i.e. SoC), not State of Health.
        # Mis-classifying SoH as BATTERY would confuse the energy
        # dashboard.
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
        # ``MEASUREMENT`` (not ``TOTAL_INCREASING``): range rises with
        # charging and falls with driving — level metric, not monotonic.
        # LTS-eligible.
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
        # One decimal: enough to read true thermal fluctuation without
        # surfacing fake precision from the upstream's noise floor.
        suggested_display_precision=1,
        metric=Metric.BATTERY_TEMPERATURE,
        value_fn=lambda t: t.battery_temperature,
    ),
    AbrpEnumSensorEntityDescription(
        key="charging_state",
        translation_key="charging_state",
        # ENUM device_class: a categorical state, not a measurement. No
        # ``state_class`` and no unit — ENUM is LTS-ineligible (accepted).
        device_class=SensorDeviceClass.ENUM,
        options=list(CHARGING_STATE_OPTIONS.values()),
        metric=Metric.CHARGING_STATE,
        value_fn=lambda t: t.charging_state,
    ),
)

SENSORS_BY_METRIC: dict[
    Metric, AbrpNumericSensorEntityDescription | AbrpEnumSensorEntityDescription
] = {description.metric: description for description in SENSORS}


def _telemetry_unique_id(
    entry: AbetterrouteplannerConfigEntry, vehicle_id: int, key: str
) -> str:
    """Build a telemetry sensor's ``unique_id`` — the ONE definition of the scheme.

    Every telemetry sensor registers under this id; the eager-from-registry
    probe and the new-vehicle poll filter both look entities up by re-deriving
    it here, so they cannot drift from what the sensors actually registered.
    """
    return f"{entry.unique_id}_{vehicle_id}_{key}"


def vehicles_without_sensors(
    hass: HomeAssistant,
    entry: AbetterrouteplannerConfigEntry,
    vehicle_ids: list[int],
) -> list[int]:
    """Return the vehicles that have no telemetry sensor in the entity registry.

    A vehicle with any previously-registered sensor is "known": the
    eager-from-registry probe recreates its entities and ``RestoreSensor``
    restores their last values, so it needs no startup poll. A vehicle with no
    registered sensors is new (fresh install or just added) and is polled once
    for initial values.
    """
    registry = er.async_get(hass)
    return [
        vehicle_id
        for vehicle_id in vehicle_ids
        if not any(
            registry.async_get_entity_id(
                "sensor",
                DOMAIN,
                _telemetry_unique_id(entry, vehicle_id, description.key),
            )
            for description in SENSORS
        )
    ]


def _extract_value(
    description: AbrpNumericSensorEntityDescription | AbrpEnumSensorEntityDescription,
    metric_value: MetricValue,
) -> float | str | None:
    """Extract a description's display value from a MetricValue (presence probe).

    Mirrors the per-subclass ``_value_from_metric`` coercion without an entity
    instance, for the setup-time seed-frame scan that decides which entities to
    create. Numeric → float; enum → mapped option string.
    """
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
    """Dispatch on the description type to the matching concrete sensor.

    Keeps the three instantiation sites (eager-from-registry probe,
    seed-frame scan, dispatcher ``_on_new_metric``) free of a repeated
    isinstance branch.
    """
    if isinstance(description, AbrpEnumSensorEntityDescription):
        return AbrpEnumSensor(coordinator, entry, vehicle_id, description)
    return AbrpNumericSensor(coordinator, entry, vehicle_id, description)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbetterrouteplannerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create telemetry sensors for the selected vehicles.

    Three creation paths: an eager-from-registry probe, a seed-frame scan, and
    the late-metric dispatcher for metrics that first appear on the stream.
    """
    runtime = entry.runtime_data
    vehicles = runtime.vehicles
    telemetry_coordinator = runtime.telemetry_coordinator

    selected_ids = {int(vehicle_id) for vehicle_id in entry.data[CONF_VEHICLE_IDS]}
    present_ids = {raw.vehicle_id for raw, _ in vehicles}

    missing = selected_ids - present_ids
    for vehicle_id in missing:
        # A selected vehicle missing from the garage snapshot is an expected
        # steady state after it is removed upstream: its device card is left
        # orphaned and the user can delete it via the integration's delete link
        # (async_remove_config_entry_device permits removal once a vehicle is
        # absent from the snapshot), while the selection retains the id until
        # the user reconfigures. Not actionable at setup, so debug rather than
        # warning. Format with the raw int so a user grepping their logs for the
        # id they saw in the picker finds it verbatim.
        _LOGGER.debug(
            "Selected vehicle %d is not in the ABRP garage; skipping",
            vehicle_id,
        )

    entity_registry = er.async_get(hass)
    added: set[tuple[int, Metric]] = set()
    entities: list[SensorEntity] = []
    for raw, _ in vehicles:
        vehicle_id = raw.vehicle_id
        if vehicle_id not in selected_ids:
            continue
        # Eager-from-registry probe: a prior session recorded entities for
        # wake-only metrics (voltage, power, SoH, ...) that are silent
        # until the vehicle wakes. Without this probe a parked vehicle
        # would flash ``Unavailable`` for hours across restart until the
        # next wake event recreates them lazily. ``RestoreSensor`` then
        # lifts the recorder's last value back into ``native_value`` in
        # ``async_added_to_hass``. Marked seen so the dispatcher does
        # not double-create when the next frame arrives.
        for description in SENSORS:
            unique_id = _telemetry_unique_id(entry, vehicle_id, description.key)
            entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id is None:
                continue
            # Defense-in-depth: the registry is keyed globally
            # by ``(domain, platform, unique_id)``; the ABRP unique_id
            # scope formula uses ``entry.unique_id`` (OIDC ``sub``), not
            # ``entry.entry_id``, so a foreign config entry sharing the
            # same OIDC sub would surface its row here. Config-flow
            # ``_abort_if_unique_id_configured`` makes that impossible
            # today, but the filter keeps the rejection deterministic
            # at the integration boundary against any future HA core
            # change that admits the rebind.
            entry_row = entity_registry.async_get(entity_id)
            if entry_row is None or entry_row.config_entry_id != entry.entry_id:
                continue
            entities.append(
                _build_telemetry_sensor(
                    telemetry_coordinator, entry, vehicle_id, description
                )
            )
            added.add((vehicle_id, description.metric))
            telemetry_coordinator.mark_metric_seen(vehicle_id, description.metric)
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
            telemetry_coordinator.mark_metric_seen(vehicle_id, description.metric)

    # mark_metric_seen MUST run before register_presence_predicates: once the
    # predicates are live, the next pushed update compares against
    # ``_presence_seen`` and a missing pre-add entry would cause a duplicate
    # async_add_entities for an already-created entity.
    telemetry_coordinator.register_presence_predicates(
        {description.metric for description in SENSORS}
    )

    @callback
    def _on_new_metric(vehicle_id: int, metric: Metric) -> None:
        """Create a metric sensor on its first observed non-None frame.

        ``mark_metric_seen`` is deferred to AFTER ``async_add_entities`` so
        a transient skip (vehicle not yet visible in the garage payload,
        no longer selected after a reconfigure, etc.) does not permanently
        suppress dispatches for this ``(vehicle_id, metric)`` — the
        next non-None frame re-fires and reaches this listener again.

        ``signal_new_metric`` is a shared dispatcher that any platform may
        register a presence predicate on (only the sensor platform does today;
        device_tracker is planned), so a ``metric`` outside
        ``SENSORS_BY_METRIC`` is some other platform's dispatch — ignore it.
        """
        if metric not in SENSORS_BY_METRIC:
            return
        if (vehicle_id, metric) in added:
            return
        if vehicle_id not in selected_ids:
            return
        description = SENSORS_BY_METRIC[metric]
        if vehicle_id not in present_ids:
            return
        added.add((vehicle_id, metric))
        async_add_entities(
            [
                _build_telemetry_sensor(
                    telemetry_coordinator, entry, vehicle_id, description
                )
            ]
        )
        telemetry_coordinator.mark_metric_seen(vehicle_id, metric)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, signal_new_metric(entry.entry_id), _on_new_metric
        )
    )
    async_add_entities(entities)


class AbrpTelemetrySensor[T: (float, str)](
    CoordinatorEntity[AbrpTelemetryCoordinator], RestoreSensor
):
    """One telemetry sensor (soc / power / voltage / charging_state) per vehicle.

    Generic over the extracted value type ``T`` — ``float`` for the numeric
    metrics, ``str`` for the categorical ENUM metric. All shared behaviour
    (lazy-create, restore, ``extra_state_attributes``, ``available``,
    live-wins-over-restored) lives here; the only divergence is the
    restore-value coercion in :meth:`_restore_native_value` and the live-value
    coercion in :meth:`_value_from_metric`, overridden by the concrete
    subclasses.

    Restores the last-known ``native_value`` and ``last_reported_at`` across
    HA restarts so wake-only fields (voltage, power, SoH, charging_state, ...)
    keep their most recent reading visible while the vehicle is parked and
    ABRP is silent. Live coordinator frames win over restored slots whenever
    the metric carries a non-None value.
    """

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
        # Same device identifier shape as the anchor pass in
        # ``async_setup_entry`` so HA links every telemetry entity for
        # this vehicle to the device created there.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, scope)},
        )
        self._restored_native_value: T | None = None
        self._restored_last_reported_at: datetime | None = None
        self._restored_provider: str | None = None

    def _restore_native_value(self, raw: object) -> T | None:
        """Coerce a recorder-cached ``native_value`` to ``T`` (or ``None``).

        Overridden per concrete subclass: numerics accept int/float (not
        bool); the enum accepts only an in-``options`` string.
        """
        raise NotImplementedError

    def _value_from_metric(self, metric_value: MetricValue) -> T | None:
        """Coerce a live ``MetricValue`` to this sensor's display ``T``.

        Overridden per concrete subclass: numerics return the float reading;
        the enum maps the ``ChargingState`` to its HA option string.
        """
        raise NotImplementedError

    @override
    async def async_added_to_hass(self) -> None:
        """Lift recorder-cached value + stamp into per-instance restore slots.

        Wake-only telemetry does not push every minute — between wake
        events the upstream is silent. Restoration keeps the last-known
        reading visible across HA restart rather than flashing
        ``Unavailable`` for the ~16h gap users reported on parked
        vehicles. The malformed-stamp branch leaves the slot at
        ``None`` so ``extra_state_attributes`` omits the key entirely
        (beats both expose-as-is and surfacing ``None``).
        """
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None:
            self._restored_native_value = self._restore_native_value(last.native_value)
        if (state := await self.async_get_last_state()) is not None:
            stamp_raw = state.attributes.get("last_reported_at")
            # ``state.attributes`` round-trips through HA's JSONEncoder so
            # the live ``datetime`` stamp arrives back as an ISO string.
            # Parse once; on failure leave the slot at the class-default
            # ``None`` so the attribute is omitted.
            if isinstance(stamp_raw, str) and stamp_raw:
                with suppress(ValueError):
                    self._restored_last_reported_at = datetime.fromisoformat(stamp_raw)
            # Symmetric-reject restore guard for the ``provider``
            # claim — mirrors the wire-boundary filter in the
            # coordinator. ``int``, ``bool``, ``dict``,
            # ``list``, ``None``, and the empty string all map to "no
            # restored provider"; the attribute is then omitted by
            # ``extra_state_attributes`` rather than surfacing as
            # ``provider: null``.
            provider_raw = state.attributes.get("provider")
            if _is_clean_provider_str(provider_raw):
                self._restored_provider = provider_raw

    @property
    @override
    def native_value(self) -> StateType:
        """Live value when present, falling back to the restored value.

        Annotated ``StateType`` (not ``T | None``) so HA's pylint
        ``home-assistant-return-type`` plugin — which checks the literal
        annotation and does not resolve the TypeVar — accepts it. ``T | None``
        (``T`` constrained to ``float | str``) is assignable to ``StateType``,
        so the runtime contract is unchanged. Mirrors ``airos/sensor.py``.
        """
        tlm = self.coordinator.data.get(self._vehicle_id)
        if tlm is not None:
            metric_value = self.entity_description.value_fn(tlm)
            if metric_value is not None:
                live = self._value_from_metric(metric_value)
                if live is not None:
                    return live
        return self._restored_native_value

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Compose ``last_reported_at`` + ``provider`` (live-wins).

        Returns native ``datetime`` for the stamp — HA's ``JSONEncoder``
        serialises to ISO at persist time, and the frontend renders
        relative time + history correctly only on typed datetime. The
        fallback from live to restored is per-attribute, NOT whole dict:
        a live frame that carries the metric but omits ``provider`` keeps
        the restored provider AND picks up the live ``last_reported_at``
        simultaneously. When every slot is empty, returns ``None``
        (whole-mapping omission) so attributes are absent rather than
        rendering as ``null``.
        """
        attrs: dict[str, Any] = {}
        live_stamp = self.coordinator.last_reported_at.get(self._vehicle_id, {}).get(
            self._metric
        )
        stamp = (
            live_stamp if live_stamp is not None else self._restored_last_reported_at
        )
        if stamp is not None:
            attrs["last_reported_at"] = stamp
        live_provider = self.coordinator.last_provider.get(self._vehicle_id, {}).get(
            self._metric
        )
        provider = (
            live_provider if live_provider is not None else self._restored_provider
        )
        if provider is not None:
            attrs["provider"] = provider
        return attrs or None

    @property
    @override
    def available(self) -> bool:
        """True whenever a live OR restored value is surfacing.

        Decoupled from ``CoordinatorEntity.available`` (which gates on
        ``last_update_success``) — restoration's whole point is to keep
        the entity meaningful when the upstream is silent or HA just
        restarted before any frame landed.
        """
        return self.native_value is not None


class AbrpNumericSensor(AbrpTelemetrySensor[float]):
    """A numeric telemetry sensor (soc / power / voltage / ...)."""

    entity_description: AbrpNumericSensorEntityDescription

    @override
    def _restore_native_value(self, raw: object) -> float | None:
        """Accept an int/float recorder value (rejecting bool), else ``None``.

        ``bool`` is a subclass of ``int`` in Python, so the explicit
        ``isinstance(raw, bool)`` exclusion stops a malformed ``True`` from
        surfacing as ``1.0``.
        """
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
        return None

    @override
    def _value_from_metric(self, metric_value: MetricValue) -> float | None:
        """Return the numeric reading; ignore a non-float value defensively.

        Numeric metrics always carry a ``float`` ``value`` in the library's
        contract; the isinstance guard (excluding ``bool``) is belt-and-suspenders
        against a future metric mis-binding rather than an expected branch.
        """
        value = metric_value.value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None


class AbrpEnumSensor(AbrpTelemetrySensor[str]):
    """The categorical ENUM telemetry sensor (charging_state)."""

    entity_description: AbrpEnumSensorEntityDescription

    @override
    def _restore_native_value(self, raw: object) -> str | None:
        """Accept a restored string only when it is a current ``options`` member.

        Belt-and-suspenders mirroring HA core's ENUM rejection: a restored
        value outside ``options`` (e.g. the raw UPPER wire member, or junk
        from a renamed option) is coerced to ``None`` rather than written
        back — an out-of-``options`` value would make HA core raise
        ``ValueError`` at state write.
        """
        options = self.entity_description.options or ()
        return raw if isinstance(raw, str) and raw in options else None

    @override
    def _value_from_metric(self, metric_value: MetricValue) -> str | None:
        """Map the library ``ChargingState`` to this integration's option string.

        Returns ``None`` for a non-``ChargingState`` value (defensive) so a
        mis-bound metric surfaces as unavailable rather than raising.
        """
        value = metric_value.value
        if isinstance(value, ChargingState):
            return CHARGING_STATE_OPTIONS.get(value)
        return None
