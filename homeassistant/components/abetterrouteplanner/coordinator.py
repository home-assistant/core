"""DataUpdateCoordinators for the A Better Routeplanner integration.

Two coordinators back the integration:

* :class:`AbrpVehiclesCoordinator` polls the authenticated user's garage
  every :data:`SCAN_INTERVAL` via :meth:`aioabrp.AbrpClient.async_get_vehicles`
  and resolves each vehicle's device-card strings by calling
  :meth:`aioabrp.AbrpClient.async_get_vehicle_model_display` per typecode
  (HA-side device-card composition — see :mod:`.device_info`). The garage
  rarely changes — vehicles are added or removed manually in the ABRP web
  app — so a 10-minute interval keeps the rate-limit footprint negligible
  while still picking up additions/removals within one HA dashboard reload.
* :class:`AbrpTelemetryCoordinator` is a thin push-mode coordinator. The
  :class:`aioabrp.TelemetryStream` (built in ``__init__``) drives state in
  through :meth:`AbrpTelemetryCoordinator.on_update` /
  :meth:`AbrpTelemetryCoordinator.on_connection_change`; this module owns no
  reconnect / merge / staleness machinery — that all lives in the library.
"""

import asyncio
from collections.abc import Iterable
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpClient,
    AbrpVehicle,
    ConnectionEvent,
    ConnectionState,
    Metric,
    Telemetry,
    VehicleModelDisplay,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .auth import AbetterrouteplannerAuth
from .const import ABRP_APP_KEY, DOMAIN, signal_new_metric
from .device_info import ComposedDeviceInfo, compose_device_info

if TYPE_CHECKING:
    from . import AbetterrouteplannerConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=10)


class GarageVehicle:
    """One garage vehicle joined with its composed HA device-card fields.

    The :class:`aioabrp.AbrpVehicle` returned by the library carries only the
    raw identity fields (``vehicle_id`` / ``name`` / ``vehicle_model`` /
    ``paint``) and no composed ``device_model`` / ``device_manufacturer``
    columns. This carrier holds the raw vehicle alongside the
    :class:`.device_info.ComposedDeviceInfo` produced by joining its typecode
    against the v2 catalog.

    Identity attributes (``vehicle_id`` / ``name`` / ``vehicle_model``) are
    re-exported as read-only properties so existing call sites in
    ``__init__`` / ``sensor`` keep reading ``item.vehicle_id`` etc. unchanged;
    ``device_model`` / ``device_manufacturer`` resolve from the composed pair.
    """

    __slots__ = ("device_manufacturer", "device_model", "vehicle")

    def __init__(self, vehicle: AbrpVehicle, composed: ComposedDeviceInfo) -> None:
        """Join a raw vehicle with its composed device-card fields."""
        self.vehicle = vehicle
        self.device_model = composed.device_model
        self.device_manufacturer = composed.device_manufacturer

    @property
    def vehicle_id(self) -> int:
        """Return the upstream vehicle id."""
        return self.vehicle.vehicle_id

    @property
    def name(self) -> str | None:
        """Return the user-set vehicle nickname, if any."""
        return self.vehicle.name

    @property
    def vehicle_model(self) -> str:
        """Return the raw vehicle typecode."""
        return self.vehicle.vehicle_model

    def __eq__(self, other: object) -> bool:
        """Compare by value over the raw vehicle + composed device fields.

        Value equality is load-bearing: the polling garage coordinator is a
        ``TimestampDataUpdateCoordinator`` that suppresses listener fires when
        a poll returns ``previous_data == self.data``. Without an explicit
        ``__eq__`` this ``__slots__`` class falls back to identity, so every
        10-min poll would compare unequal and spuriously re-fire the
        stale-device / auto-add / rename listeners on an unchanged garage.
        ``AbrpVehicle`` is a frozen value-equal dataclass, so this fully
        restores the old suppression.
        """
        if not isinstance(other, GarageVehicle):
            return NotImplemented
        return (self.vehicle, self.device_model, self.device_manufacturer) == (
            other.vehicle,
            other.device_model,
            other.device_manufacturer,
        )

    def __hash__(self) -> int:
        """Hash over the same fields as :meth:`__eq__`."""
        return hash((self.vehicle, self.device_model, self.device_manufacturer))


class AbrpVehiclesCoordinator(TimestampDataUpdateCoordinator[list[GarageVehicle]]):
    """Fetch the authenticated user's ABRP garage on a fixed interval."""

    config_entry: AbetterrouteplannerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AbetterrouteplannerConfigEntry,
        session: OAuth2Session,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._session = session
        self._client = AbrpClient(
            async_get_clientsession(hass),
            ABRP_APP_KEY,
            AbetterrouteplannerAuth(session),
        )

    async def _async_update_data(self) -> list[GarageVehicle]:
        """Fetch the garage and compose each vehicle's device-card fields.

        The :class:`.auth.AbetterrouteplannerAuth` wrapper handles the OAuth
        token refresh and maps a revoked/rotated refresh token to
        :class:`aioabrp.AbrpAuthError`; here that surfaces as
        :class:`ConfigEntryAuthFailed`. Other garage API failures map to
        :class:`UpdateFailed`.

        Per-typecode display metadata is fetched fresh for every vehicle on
        every poll (no cache, by design). A per-vehicle display failure
        degrades only that vehicle to the raw-typecode fallback (see
        :func:`.device_info.compose_device_info`) and never fails the refresh.
        """
        try:
            raw_vehicles = await self._client.async_get_vehicles()
        except AbrpAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="abrp_session_invalid",
            ) from err
        except AbrpApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="abrp_update_failed",
            ) from err

        displays = await self._async_fetch_displays(raw_vehicles)
        return [
            GarageVehicle(raw, compose_device_info(display))
            for raw, display in zip(raw_vehicles, displays, strict=True)
        ]

    async def _async_fetch_displays(
        self, raw_vehicles: list[AbrpVehicle]
    ) -> list[VehicleModelDisplay | None]:
        """Resolve each vehicle's display metadata, degrading per-vehicle.

        Calls :meth:`aioabrp.AbrpClient.async_get_vehicle_model_display` per
        vehicle in parallel via :func:`asyncio.gather` with
        ``return_exceptions=True`` so one typecode's failure does not block the
        rest. Any failure maps to ``None`` (the vehicle's device card then
        falls back to the raw typecode):

        * a 404 for a typecode ABRP does not catalog (``AbrpApiError``),
        * a transient API / transport / timeout failure, or
        * an ``AbrpAuthError``.

        Auth errors are NOT propagated to reauth from here: the garage fetch
        above already maps auth failure to :class:`ConfigEntryAuthFailed`, and
        the telemetry stream is the authoritative reauth trigger; surfacing it
        from here too would race two reauth flows. Each failure logs at DEBUG —
        this is per-vehicle, so a global outage would emit one line per
        vehicle; DEBUG keeps that quiet (consistent with
        :meth:`AbrpTelemetryCoordinator.async_seed`).
        """
        results = await asyncio.gather(
            *(
                self._client.async_get_vehicle_model_display(raw.vehicle_model)
                for raw in raw_vehicles
            ),
            return_exceptions=True,
        )
        displays: list[VehicleModelDisplay | None] = []
        for raw, result in zip(raw_vehicles, results, strict=True):
            if isinstance(result, AbrpAuthError):
                _LOGGER.debug(
                    "Display metadata for typecode %s rejected (%s); device "
                    "card falls back to the raw typecode",
                    raw.vehicle_model,
                    result,
                )
                displays.append(None)
                continue
            if isinstance(result, (AbrpApiError, TimeoutError)):
                _LOGGER.debug(
                    "Display metadata for typecode %s failed (%s); device "
                    "card falls back to the raw typecode",
                    raw.vehicle_model,
                    result,
                )
                displays.append(None)
                continue
            if isinstance(result, BaseException):
                # ``BaseException`` (not ``Exception``) so ``CancelledError`` /
                # ``KeyboardInterrupt`` / ``SystemExit`` propagate cleanly
                # rather than being silently turned into "no display".
                if isinstance(result, Exception):
                    _LOGGER.warning(
                        "Unexpected display-metadata failure for typecode %s: %s",
                        raw.vehicle_model,
                        result,
                    )
                    displays.append(None)
                    continue
                raise result
            displays.append(result)
        return displays


class AbrpTelemetryCoordinator(TimestampDataUpdateCoordinator[dict[int, Telemetry]]):
    """Thin push-mode coordinator for the v2 telemetry stream.

    Holds the current per-vehicle telemetry snapshot keyed by
    ``vehicle_id`` as a :class:`aioabrp.Telemetry` struct. The
    :class:`aioabrp.TelemetryStream` (constructed in ``__init__``) calls
    :meth:`on_update` per frame batch and :meth:`on_connection_change` on
    connection-state transitions. ``update_interval`` is ``None`` because the
    push model means HA never polls this coordinator.
    """

    config_entry: AbetterrouteplannerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AbetterrouteplannerConfigEntry,
    ) -> None:
        """Initialize the telemetry coordinator with an empty per-vehicle map."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} telemetry",
            update_interval=None,
        )
        self.data = {}
        # Metrics whose first appearance per vehicle should fire
        # ``signal_new_metric`` for lazy entity creation. The sensor platform
        # contributes its keys via :meth:`register_presence_predicates`.
        self._presence_metrics: set[Metric] = set()
        # ``(vehicle_id, Metric)`` pairs already dispatched / created so the
        # first-appearance dispatch fires exactly once per pair.
        self._presence_seen: set[tuple[int, Metric]] = set()
        # Per-vehicle, per-metric wall-clock RECEIPT time of the most recent
        # frame carrying the metric. Sensor's ``extra_state_attributes``
        # surfaces this as ``last_reported_at``.
        self.last_reported_at: dict[int, dict[Metric, datetime]] = {}
        # Per-vehicle, per-metric upstream provider string from the most
        # recent frame that carried a usable provider for this metric.
        # Sticky on omission: a metric present without a provider RETAINS
        # the prior value rather than blanking it. Provider rarely flips
        # mid-stream; transient absence shouldn't blank the user-visible
        # signal.
        self.last_provider: dict[int, dict[Metric, str]] = {}
        # In-memory connection triage retained for the future diagnostics PR.
        # ``last_connection_event`` is the most recent ``ConnectionEvent``;
        # ``last_connection_at`` its receipt time; ``connect_count`` bumps on
        # each CONNECTED transition.
        self.last_connection_event: ConnectionEvent | None = None
        self.last_connection_at: datetime | None = None
        self.connect_count: int = 0

    @callback
    def forget_vehicle(self, vehicle_id: int) -> None:
        """Clear every per-vehicle surface for ``vehicle_id``.

        Wired to the stale-devices removal path in
        :func:`__init__._remove_stale_devices` so the in-memory state stays
        honest with the device registry. ``.pop(.., None)`` semantics —
        calling for an unknown vid is a no-op so a vehicle that never
        surfaced a telemetry frame can still be removed without raising.

        Sweeps four surfaces: the telemetry snapshot, the per-metric
        ``last_reported_at`` and ``last_provider`` maps, and any
        ``(vehicle_id, *)`` entries in ``_presence_seen`` so a re-added
        vehicle re-fires its create-on-first-frame dispatch.
        ``async_set_updated_data`` is intentionally NOT invoked — the
        stale-devices flow has already removed the device + its entities.
        """
        self.data.pop(vehicle_id, None)
        self.last_reported_at.pop(vehicle_id, None)
        self.last_provider.pop(vehicle_id, None)
        self._presence_seen -= {
            pair for pair in self._presence_seen if pair[0] == vehicle_id
        }

    @callback
    def register_presence_predicates(self, metrics: Iterable[Metric]) -> None:
        """Register the metrics whose first appearance triggers entity creation.

        Presence is now :class:`aioabrp.Metric`-membership: a metric present
        in an :meth:`on_update` payload is "seen". The sensor platform
        contributes the metric keys it cares about; ``.update`` merges them
        into the shared set so platforms accumulate rather than clobber.

        From the first call onwards :meth:`on_update` fires the dispatcher
        signal on the first appearance of each ``(vehicle_id, Metric)`` pair.
        """
        self._presence_metrics.update(metrics)

    @callback
    def mark_metric_seen(self, vehicle_id: int, metric: Metric) -> None:
        """Record a ``(vehicle_id, Metric)`` pair as already-emitted.

        Called by the sensor platform for every entity it creates during the
        post-pre-warm inspection so the dispatcher does not double-fire when
        the next frame carries the same metric.
        """
        self._presence_seen.add((vehicle_id, metric))

    @callback
    def _apply_metrics(self, vehicle_id: int, delta: Telemetry) -> None:
        """Apply a typed Telemetry delta to the per-vehicle state (no notify).

        Shared assignment path for :meth:`on_update` (stream) and
        :meth:`async_seed` (best-effort one-shot poll). Merges ``delta``
        into the stored :class:`aioabrp.Telemetry` for the vehicle, stamps
        ``last_reported_at`` with the RECEIPT time for each present metric,
        updates ``last_provider`` only when the delta carried a provider
        (sticky-on-omission). Fires ``signal_new_metric`` on the first
        appearance of each ``(vehicle_id, metric)`` pair.

        Does NOT notify coordinator listeners — the caller decides (the
        stream path stamps + notifies via :meth:`on_update`; the seed path
        applies silently before the platform is forwarded).
        """
        # ``Telemetry.items()`` yields only present (non-None) fields, so an
        # empty iterator means this frame carries no metrics — nothing to apply.
        if next(delta.items(), None) is None:
            return
        now = dt_util.utcnow()
        stored = self.data.get(vehicle_id)
        self.data[vehicle_id] = delta if stored is None else stored.merge(delta)
        reported = self.last_reported_at.setdefault(vehicle_id, {})
        providers = self.last_provider.setdefault(vehicle_id, {})
        signal = signal_new_metric(self.config_entry.entry_id)
        for metric, metric_value in delta.items():
            # Receipt time, NOT the wire ``time`` — ``last_reported_at`` is
            # "when did HA last see this field", per today's policy.
            reported[metric] = now
            if metric_value.provider is not None:
                providers[metric] = metric_value.provider
            if (
                metric in self._presence_metrics
                and (vehicle_id, metric) not in self._presence_seen
            ):
                # Per-frame fan-out is un-debounced by design: ABRP's
                # telemetry cadence is low (seconds-to-minutes between
                # frames), so a Debouncer buys nothing. If frame rate is ever
                # observed high, wrap the dispatch + notify in one.
                async_dispatcher_send(self.hass, signal, vehicle_id, metric)

    @callback
    def on_update(self, vehicle_id: int, telemetry: Telemetry) -> None:
        """Apply one stream frame and notify coordinator listeners.

        Sync callback handed to :class:`aioabrp.TelemetryStream`. Applies the
        :class:`aioabrp.Telemetry` delta through the shared
        :meth:`_apply_metrics` path, then pushes the new snapshot to entity
        listeners and stamps the diagnostics ``last_update_success_time`` with
        the receipt time (the highest-value push-stream triage signal —
        ``async_set_updated_data`` does not invoke the polling-path
        ``_async_refresh_finished`` that would otherwise set it).
        """
        # ``Telemetry.items()`` yields only present (non-None) fields, so an
        # empty iterator means an empty frame — skip the notify fan-out.
        if next(telemetry.items(), None) is None:
            return
        self._apply_metrics(vehicle_id, telemetry)
        now = dt_util.utcnow()
        self.async_set_updated_data(self.data)
        self.last_update_success_time = now

    @callback
    def on_connection_change(self, event: ConnectionEvent) -> None:
        """Record a stream connection-state transition.

        Sync callback handed to :class:`aioabrp.TelemetryStream`. Availability
        is value-based (``native_value is not None``) and DELIBERATELY ignores
        the connection state — the ABRP server closes idle streams (~200 s) as
        steady-state, so a DISCONNECTED event only logs and never marks
        entities unavailable. This method feeds only:

        * once-per-transition INFO logging (don't spam — log only on a state
          change versus the last recorded event);
        * ``AUTH_FAILED`` → trigger reauth via ``async_start_reauth``;
        * the in-memory triage fields retained for the future diagnostics PR.
        """
        previous = self.last_connection_event
        changed = previous is None or previous.state is not event.state
        self.last_connection_event = event
        self.last_connection_at = dt_util.utcnow()
        if event.state is ConnectionState.CONNECTED:
            self.connect_count += 1

        if changed:
            if event.state is ConnectionState.CONNECTED:
                _LOGGER.info("ABRP telemetry stream connected")
            elif event.state is ConnectionState.DISCONNECTED:
                _LOGGER.info(
                    "ABRP telemetry stream disconnected (%s)",
                    event.reason or "no reason given",
                )
            elif event.state is ConnectionState.AUTH_FAILED:
                _LOGGER.warning(
                    "ABRP telemetry stream auth failed (%s); triggering reauth",
                    event.reason or "no reason given",
                )

        if event.state is ConnectionState.AUTH_FAILED:
            self.config_entry.async_start_reauth(self.hass)

    async def async_seed(self, client: AbrpClient, vehicle_ids: Iterable[int]) -> None:
        """Best-effort seed of the per-vehicle map via one-shot telemetry.

        Seeding is HA-side policy — the library does not seed. Calls
        :meth:`aioabrp.AbrpClient.async_get_current_telemetry` per vehicle in
        parallel via :func:`asyncio.gather` with ``return_exceptions=True`` so
        one vehicle's failure doesn't block the rest. Failures log and skip;
        the stream subsequently overwrites stale seeds as frames arrive.

        Results apply through the same :meth:`_apply_metrics` path as
        :meth:`on_update` so seed and stream share one assignment code path.
        Auth errors are NOT propagated to reauth from here — the stream
        reaches the same failure and triggers reauth via
        :meth:`on_connection_change`; surfacing it from both sites would race
        two reauth flows.
        """
        ids = list(vehicle_ids)
        if not ids:
            return
        results = await asyncio.gather(
            *(client.async_get_current_telemetry(vid) for vid in ids),
            return_exceptions=True,
        )
        for vehicle_id, result in zip(ids, results, strict=True):
            if isinstance(result, AbrpAuthError):
                # DEBUG, not WARNING: a globally revoked token would emit one
                # of these per vehicle (N warnings for N vehicles). The
                # stream's single AUTH_FAILED event is the real reauth signal.
                _LOGGER.debug(
                    "Telemetry seed for vehicle %d rejected (%s); stream will retry",
                    vehicle_id,
                    result,
                )
                continue
            if isinstance(result, AbrpApiError):
                _LOGGER.debug(
                    "Telemetry seed for vehicle %d failed (%s); skipping",
                    vehicle_id,
                    result,
                )
                continue
            if isinstance(result, BaseException):
                # ``BaseException`` (not ``Exception``) so ``CancelledError`` /
                # ``KeyboardInterrupt`` / ``SystemExit`` propagate cleanly
                # through unload / Ctrl-C rather than being silently turned
                # into "no seed for this vehicle".
                if isinstance(result, Exception):
                    _LOGGER.warning(
                        "Unexpected telemetry seed failure for vehicle %d: %s",
                        vehicle_id,
                        result,
                    )
                    continue
                raise result
            self._apply_metrics(vehicle_id, result)
