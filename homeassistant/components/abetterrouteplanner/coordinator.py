"""DataUpdateCoordinators for the A Better Routeplanner integration.

Two coordinators back the integration:

* :class:`AbrpVehiclesCoordinator` polls the authenticated user's garage
  every :data:`SCAN_INTERVAL` via :meth:`aioabrp.AbrpClient.async_get_vehicles`
  and joins each raw vehicle against the v2 catalog (HA-side device-model
  composition — see :mod:`.device_info`). The garage rarely changes —
  vehicles are added or removed manually in the ABRP web app — so a
  10-minute interval keeps the rate-limit footprint negligible while still
  picking up additions/removals within one HA dashboard reload.
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
    CatalogEntry,
    ConnectionEvent,
    ConnectionState,
    Metric,
    MetricValue,
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
        # Lazy-loaded v2 vehicle catalog (typecode → CatalogEntry). Fetched
        # once on the first refresh that successfully reaches the client;
        # ``None`` means "not yet attempted", ``{}`` means "fetch failed —
        # degrade to empty catalog for the rest of this session". Config
        # entry reload is the only refresh path; mid-session ABRP catalog
        # changes are picked up next reload.
        self._catalog: dict[str, CatalogEntry] | None = None

    async def _async_update_data(self) -> list[GarageVehicle]:
        """Fetch the garage, lazy-load the catalog, and compose device fields.

        The :class:`.auth.AbetterrouteplannerAuth` wrapper handles the OAuth
        token refresh and maps a revoked/rotated refresh token to
        :class:`aioabrp.AbrpAuthError`; here that surfaces as
        :class:`ConfigEntryAuthFailed`. Other API failures map to
        :class:`UpdateFailed`.
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

        if self._catalog is None:
            try:
                self._catalog = await self._client.async_get_catalog()
            except (AbrpAuthError, AbrpApiError, TimeoutError) as err:
                # Non-fatal: catalog endpoint may rate-limit independently of
                # the garage endpoint. Degrade to an empty catalog so every
                # typecode misses and ``DeviceInfo.model`` falls back to the
                # raw ``vehicle_model`` typecode on the device card. Garage
                # data is unaffected so the telemetry path keeps working.
                # Retry happens on the next config-entry reload, not on the
                # next coordinator poll (cache is now ``{}``, not ``None``).
                #
                # ``TimeoutError`` is named explicitly as defense-in-depth:
                # the client already wraps a naked ``asyncio.TimeoutError`` as
                # ``AbrpApiError`` at its boundary, so under normal flow no
                # TimeoutError reaches this band. The explicit name guards
                # against any future code path that bypasses the wrapper — a
                # regression there would otherwise crash the entire refresh
                # and freeze ``self._catalog`` at ``None`` (force unbounded
                # retry).
                _LOGGER.warning(
                    "ABRP catalog fetch failed; DeviceInfo.model will fall "
                    "back to the raw type code until the next integration "
                    "reload: %s",
                    err,
                )
                self._catalog = {}

        return [
            GarageVehicle(raw, compose_device_info(raw, self._catalog))
            for raw in raw_vehicles
        ]


class AbrpTelemetryCoordinator(
    TimestampDataUpdateCoordinator[dict[int, dict[Metric, MetricValue]]]
):
    """Thin push-mode coordinator for the v2 telemetry stream.

    Holds the current per-vehicle telemetry snapshot keyed by
    ``vehicle_id`` then :class:`aioabrp.Metric`. The
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
    def _apply_metrics(
        self, vehicle_id: int, metrics: dict[Metric, MetricValue]
    ) -> None:
        """Apply a typed metric batch to the per-vehicle state (no notify).

        Shared assignment path for :meth:`on_update` (stream) and
        :meth:`async_seed` (best-effort one-shot poll). For each
        ``(metric, MetricValue)``: store the value, stamp ``last_reported_at``
        with the RECEIPT time, and update ``last_provider`` only when the
        frame carried a provider (sticky-on-omission). Fires
        ``signal_new_metric`` on the first appearance of each
        ``(vehicle_id, metric)`` pair.

        Does NOT notify coordinator listeners — the caller decides (the
        stream path stamps + notifies via :meth:`on_update`; the seed path
        applies silently before the platform is forwarded).
        """
        if not metrics:
            return
        now = dt_util.utcnow()
        vehicle_data = self.data.setdefault(vehicle_id, {})
        reported = self.last_reported_at.setdefault(vehicle_id, {})
        providers = self.last_provider.setdefault(vehicle_id, {})
        signal = signal_new_metric(self.config_entry.entry_id)
        for metric, metric_value in metrics.items():
            vehicle_data[metric] = metric_value
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
    def on_update(self, vehicle_id: int, metrics: dict[Metric, MetricValue]) -> None:
        """Apply one stream frame batch and notify coordinator listeners.

        Sync callback handed to :class:`aioabrp.TelemetryStream`. Applies the
        batch through the shared :meth:`_apply_metrics` path, then pushes the
        new snapshot to entity listeners and stamps the diagnostics
        ``last_update_success_time`` with the receipt time (the highest-value
        push-stream triage signal — ``async_set_updated_data`` does not invoke
        the polling-path ``_async_refresh_finished`` that would otherwise set
        it).
        """
        if not metrics:
            return
        self._apply_metrics(vehicle_id, metrics)
        now = dt_util.utcnow()
        # ``self.data`` is deliberately mutated in place by ``_apply_metrics``;
        # this call exists purely to fan out the listener notification (push
        # coordinator — no fresh dict is built per frame).
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
