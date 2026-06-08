"""Device tracker platform for the A Better Routeplanner integration.

One :class:`AbrpDeviceTracker` per selected vehicle, sourced from the SSE
telemetry coordinator's ``location.{lat,long}`` field. Lazy-created via the
same dispatcher pattern as the sensor platform: an entity registers only
when a non-null location first arrives — at setup-time inspection (seed +
pre-warm window) or on a later SSE frame via ``signal_new_metric``.

The presence test is predicate-evaluated (:func:`_extract_lat_long`
returns ``None`` for missing / partial / non-numeric / boolean-shaped
values), not raw key existence — a frame with ``location: {time: 12345}``
must not silently freeze the entity before real coordinates ever arrive.
"""

from contextlib import suppress
from datetime import datetime
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AbetterrouteplannerConfigEntry
from ._sensor_value_fns import LOCATION_KEY, _extract_lat_long, _is_clean_provider_str
from .api import AbrpVehicle
from .const import CONF_VEHICLE_IDS, DOMAIN, signal_new_metric
from .coordinator import AbrpTelemetryCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbetterrouteplannerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Lazy-create one device_tracker per vehicle with non-null location."""
    runtime = entry.runtime_data
    garage_coordinator = runtime.garage_coordinator
    telemetry_coordinator = runtime.telemetry_coordinator
    selected_ids = {int(vehicle_id) for vehicle_id in entry.data[CONF_VEHICLE_IDS]}

    entity_registry = er.async_get(hass)
    added: set[int] = set()
    entities: list[AbrpDeviceTracker] = []
    for vehicle in garage_coordinator.data:
        if vehicle.vehicle_id not in selected_ids:
            continue
        # Eager-from-registry probe: a prior session recorded a tracker
        # for this vehicle. Wake-only GPS frames go silent for hours
        # between drives — without the eager-create, a parked vehicle
        # would surface ``Unknown`` across HA restart until the next
        # location frame. ``RestoreEntity`` lifts the recorder's last
        # lat/long back via ``async_added_to_hass``. Marked seen so the
        # dispatcher does not double-create when the next frame arrives
        # — two-place invariant: added set + coordinator's
        # ``_presence_seen``.
        scope = f"{entry.unique_id}_{vehicle.vehicle_id}"
        unique_id = f"{scope}_location"
        entity_id = entity_registry.async_get_entity_id(
            "device_tracker", DOMAIN, unique_id
        )
        # Defense-in-depth: registry lookup is global by
        # ``(domain, platform, unique_id)``; filter on
        # ``config_entry_id`` so a foreign entry sharing the same OIDC
        # ``sub`` (precluded today by config-flow's
        # ``_abort_if_unique_id_configured`` but cheap to keep
        # deterministic) cannot trigger an eager-create on this entry.
        # Flattened from sensor.py's negative-skip idiom: tracker's
        # registry-then-frame two-step requires fall-through on miss
        # (NOT ``continue``), so walrus is extracted to a named local
        # rather than mirroring sensor's two-stage ``continue`` shape.
        entry_row = (
            entity_registry.async_get(entity_id) if entity_id is not None else None
        )
        if entry_row is not None and entry_row.config_entry_id == entry.entry_id:
            entities.append(AbrpDeviceTracker(telemetry_coordinator, entry, vehicle))
            added.add(vehicle.vehicle_id)
            telemetry_coordinator.mark_metric_seen(vehicle.vehicle_id, LOCATION_KEY)
            continue
        frame = telemetry_coordinator.data.get(vehicle.vehicle_id)
        if frame is None or _extract_lat_long(frame) is None:
            continue
        entities.append(AbrpDeviceTracker(telemetry_coordinator, entry, vehicle))
        added.add(vehicle.vehicle_id)
        telemetry_coordinator.mark_metric_seen(vehicle.vehicle_id, LOCATION_KEY)

    # mark_metric_seen MUST run before register_presence_predicates: once the
    # predicate is live, the next apply_frame compares against
    # ``_presence_seen`` and a missing pre-add entry would cause a duplicate
    # async_add_entities for an already-created entity.
    telemetry_coordinator.register_presence_predicates(
        {LOCATION_KEY: _extract_lat_long}
    )

    @callback
    def _on_new_metric(vehicle_id: int, metric_key: str) -> None:
        """Create a tracker on the first observed non-None ``location`` frame.

        ``signal_new_metric`` is shared across every platform that registers
        a presence predicate; filter to our own key. ``mark_metric_seen``
        is deferred to AFTER ``async_add_entities`` so a transient skip
        (vehicle not in garage yet, no longer selected, etc.) does not
        permanently suppress future dispatches for this ``(vehicle, key)``.
        """
        if metric_key != LOCATION_KEY:
            return
        if vehicle_id in added:
            return
        if vehicle_id not in selected_ids:
            return
        vehicle = next(
            (v for v in garage_coordinator.data if v.vehicle_id == vehicle_id),
            None,
        )
        if vehicle is None:
            return
        added.add(vehicle_id)
        async_add_entities([AbrpDeviceTracker(telemetry_coordinator, entry, vehicle)])
        telemetry_coordinator.mark_metric_seen(vehicle_id, LOCATION_KEY)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, signal_new_metric(entry.entry_id), _on_new_metric
        )
    )
    async_add_entities(entities)


class AbrpDeviceTracker(
    CoordinatorEntity[AbrpTelemetryCoordinator], TrackerEntity, RestoreEntity
):
    """GPS device_tracker for one ABRP-tracked vehicle.

    Restores the last-known ``(lat, long)`` and ``last_reported_at``
    across HA restarts so the vehicle's position survives an overnight
    restart while ABRP is silent. Live coordinator frames win over the
    restored slots whenever ``_extract_lat_long`` returns non-None.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "location"
    _attr_source_type = SourceType.GPS
    # ``BaseTrackerEntity`` (device_tracker/config_entry.py:176) sets
    # ``_attr_entity_category = EntityCategory.DIAGNOSTIC`` for every tracker
    # by default, which buckets GPS into the per-device Diagnostic section
    # and hides it from the main entity dashboard. For an EV integration the
    # live location IS the primary user-facing surface — arrive-home /
    # depart-home automations and geofencing are the headline Use case on
    # the docs page, not diagnostic noise. Override to ``None`` so the
    # tracker surfaces on the main dashboard. No other ``device_tracker.py``
    # in core overrides this attribute (verified via
    # ``grep -rln "entity_category" homeassistant/components/*/device_tracker.py``);
    # ABRP is the first. The override mechanism itself is mainstream — e.g.
    # ``nibe_heatpump/climate.py`` uses the same ``= None`` idiom to opt out
    # of an inherited category on a different domain. mypy needs a targeted
    # ignore because ``BaseTrackerEntity`` narrows the type to
    # ``EntityCategory`` (not ``EntityCategory | None``) — same Shape A
    # situation as ``_attr_device_info`` below.
    _attr_entity_category = None  # type: ignore[assignment]
    # Class-level redeclare + targeted ``# type: ignore[assignment]`` because
    # ``BaseTrackerEntity`` narrows ``_attr_device_info: None``. ABRP has no
    # shared ``AbrpBaseEntity(CoordinatorEntity)`` mixin (over-engineered for
    # one tracker class), so the localized type-ignore is the cost. Siblings
    # that avoid the ignore via a shared base in MRO: ``ituran/entity.py:29``,
    # ``renault/entity.py:35`` (both have a base entity that owns the
    # assignment outside any TrackerEntity-bearing MRO chain).
    _attr_device_info: DeviceInfo  # type: ignore[assignment]

    def __init__(
        self,
        coordinator: AbrpTelemetryCoordinator,
        entry: AbetterrouteplannerConfigEntry,
        vehicle: AbrpVehicle,
    ) -> None:
        """Initialize the tracker for one vehicle."""
        super().__init__(coordinator)
        self._vehicle_id = vehicle.vehicle_id
        # Same scope formula as the model and telemetry sensors so HA links
        # every entity for this vehicle to the single device.
        scope = f"{entry.unique_id}_{vehicle.vehicle_id}"
        self._attr_unique_id = f"{scope}_location"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, scope)})
        self._restored_coords: tuple[float, float] | None = None
        self._restored_last_reported_at: datetime | None = None
        self._restored_provider: str | None = None

    async def async_added_to_hass(self) -> None:
        """Lift recorder-cached lat/long + stamp into per-instance restore slots.

        Wake-only GPS frames go silent for hours while parked; restoration
        keeps the last-known position visible across HA restart rather
        than flashing ``Unknown`` for the ~16h gap. ``isinstance`` +
        bool-exclusion at the restore boundary mirrors ``_extract_lat_long``
        itself: a recorder-corrupted attribute fails the type guard and
        the restored-coords slot stays ``None``. Atomic-pair semantic —
        if EITHER lat or lng fails the guard, BOTH stay ``None`` (a half-
        restored position is nonsensical and would render the tracker
        Unavailable anyway). Malformed stamp → attribute omitted entirely.
        """
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is None:
            return
        lat = state.attributes.get("latitude")
        lng = state.attributes.get("longitude")
        if (
            isinstance(lat, (int, float))
            and not isinstance(lat, bool)
            and isinstance(lng, (int, float))
            and not isinstance(lng, bool)
        ):
            # ``float(...)`` coercion at the restore boundary:
            # ``state.attributes`` round-trips through the recorder's
            # JSONEncoder, and integer-shaped values like ``0`` or ``42``
            # come back as Python ``int``. The property surface and
            # ``_extract_lat_long`` both declare ``float``; the coercion
            # keeps the live and restored paths type-symmetric.
            self._restored_coords = (float(lat), float(lng))
        stamp_raw = state.attributes.get("last_reported_at")
        if isinstance(stamp_raw, str) and stamp_raw:
            with suppress(ValueError):
                self._restored_last_reported_at = datetime.fromisoformat(stamp_raw)
        # Symmetric-reject restore guard for the ``provider`` claim
        # via :func:`_is_clean_provider_str` — one shared contract with
        # :func:`_extract_provider`.
        provider_raw = state.attributes.get("provider")
        if _is_clean_provider_str(provider_raw):
            self._restored_provider = provider_raw

    def _coords(self) -> tuple[float, float] | None:
        """Return the latest ``(lat, long)`` from the merged telemetry frame."""
        frame = self.coordinator.data.get(self._vehicle_id)
        if frame is None:
            return None
        return _extract_lat_long(frame)

    @property
    def latitude(self) -> float | None:
        """Return live latitude when present, falling back to the restored value."""
        coords = self._coords()
        if coords is not None:
            return coords[0]
        if self._restored_coords is not None:
            return self._restored_coords[0]
        return None

    @property
    def longitude(self) -> float | None:
        """Return live longitude when present, falling back to the restored value."""
        coords = self._coords()
        if coords is not None:
            return coords[1]
        if self._restored_coords is not None:
            return self._restored_coords[1]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Compose ``last_reported_at`` + ``provider`` (per-attribute live-wins).

        Returns native ``datetime`` for the stamp. The fallback is
        per-attribute: a live location frame that lacks ``provider`` keeps
        the restored provider while still picking up the live
        ``last_reported_at`` stamp. Returns ``None`` (whole-mapping
        omission) when every slot is empty so attributes are absent
        rather than rendering as ``null``.
        """
        attrs: dict[str, Any] = {}
        live_stamp = self.coordinator.last_reported_at.get(self._vehicle_id, {}).get(
            LOCATION_KEY
        )
        stamp = (
            live_stamp if live_stamp is not None else self._restored_last_reported_at
        )
        if stamp is not None:
            attrs["last_reported_at"] = stamp
        live_provider = self.coordinator.last_provider.get(self._vehicle_id, {}).get(
            LOCATION_KEY
        )
        provider = (
            live_provider if live_provider is not None else self._restored_provider
        )
        if provider is not None:
            attrs["provider"] = provider
        return attrs or None

    @property
    def available(self) -> bool:
        """True whenever a live OR restored position surfaces.

        Decoupled from ``CoordinatorEntity.available`` (which gates on
        ``last_update_success``) — restoration keeps the tracker
        meaningful through SSE outages or restart-before-first-frame.
        Matches the sensor restore pattern.
        """
        return self.latitude is not None and self.longitude is not None
