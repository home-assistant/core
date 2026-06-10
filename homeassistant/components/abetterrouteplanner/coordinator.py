"""DataUpdateCoordinator for the A Better Routeplanner integration.

Polls ``POST /1/session/get_tlm`` every :data:`SCAN_INTERVAL` and exposes the
authenticated user's garage to the sensor platform. The garage rarely
changes — vehicles are added or removed manually in the ABRP web app — so a
10-minute interval keeps the rate-limit footprint negligible while still
picking up additions/removals within one HA dashboard reload.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable, Mapping
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any, cast

from aiohttp import ClientError, ClientResponseError

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import parse_datetime, utcnow

from ._sensor_value_fns import STAMPED_VALUE_FNS, _extract_provider
from ._telemetry_models import OutputPointWithVehicleId
from .api import (
    AbrpApiError,
    AbrpAuthError,
    AbrpClient,
    AbrpTelemetryClient,
    AbrpVehicle,
    CatalogEntry,
    _enrich_with_catalog,
)
from .const import ABRP_APP_KEY, DOMAIN, signal_new_metric

if TYPE_CHECKING:
    from . import AbetterrouteplannerConfigEntry

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=10)

# Reconnect backoff for the SSE consumer. Resets to the first delay
# after at least one frame is received from a connection attempt.
_SSE_BACKOFF_SECONDS: tuple[int, ...] = (5, 10, 30, 60)

# Maximum wall-clock gap between consecutive SSE frames before the consumer
# treats the stream as stalled and forces a reconnect. Probe-confirmed
# empirical: the ABRP server emits no keepalive comments on idle streams and
# unilaterally closes at ~200 s (deterministic). This threshold sits ~100 s
# above that natural cycle — large enough that ``ClientPayloadError`` from
# the legitimate 200 s server-close always fires first on healthy paths;
# small enough that the production half-open-TCP stall (observed ≥16 h) is
# detected within ~5 minutes. Tunable upward if post-deployment telemetry
# shows legitimate active streams going silent across this window.
_SSE_FRAME_WATCHDOG_SECONDS = 300


def _summarize_exc(err: BaseException) -> str:
    """Short triage-friendly summary of an exception for the SSE state dump.

    Keeps the format predictable for diagnostics consumers — exception class
    name plus a truncated message — without surfacing potentially-long
    transport tracebacks. The 80-char cap is chosen to fit on a single line
    of typical issue-tracker rendering.
    """
    return f"{type(err).__name__}: {str(err)[:80]}"


class AbrpVehiclesCoordinator(TimestampDataUpdateCoordinator[list[AbrpVehicle]]):
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
        # Lazy-loaded v2 vehicle catalog (typecode → CatalogEntry). Fetched
        # once on the first refresh that successfully reaches the v1 client;
        # ``None`` means "not yet attempted", ``{}`` means "fetch failed —
        # degrade to empty catalog for the rest of this session". Config
        # entry reload is the only refresh path; mid-session ABRP catalog
        # changes are picked up next reload.
        self._catalog: dict[str, CatalogEntry] | None = None

    async def _async_update_data(self) -> list[AbrpVehicle]:
        """Refresh the OAuth token, fetch the garage, lazy-load + join catalog."""
        try:
            await self._session.async_ensure_token_valid()
        except ClientResponseError as err:
            # OAuth refresh tokens get rejected as 4xx when revoked/rotated;
            # surface that as reauth instead of looping in UpdateFailed.
            # Mirrors the init-path handling in ``__init__.async_setup_entry``.
            if HTTPStatus.BAD_REQUEST <= err.status < HTTPStatus.INTERNAL_SERVER_ERROR:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="oauth2_session_not_valid",
                ) from err
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="oauth2_token_refresh_failed",
            ) from err
        except ClientError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="oauth2_token_refresh_failed",
            ) from err

        client = AbrpClient(
            async_get_clientsession(self.hass),
            ABRP_APP_KEY,
            self._session.token["access_token"],
        )
        try:
            raw_vehicles = await client.async_get_vehicles()
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
                self._catalog = await client.async_get_catalog()
            except (AbrpAuthError, AbrpApiError, TimeoutError) as err:
                # Non-fatal: catalog endpoint may rate-limit independently of
                # the v1 garage endpoint. Degrade to an empty catalog so every
                # typecode misses and ``DeviceInfo.model`` falls back to the
                # raw ``vehicle_model`` typecode on the device card. v1 garage
                # data is unaffected so the SSE telemetry path keeps
                # working. Retry happens on the next
                # config-entry reload, not on the next coordinator poll
                # (cache is now ``{}``, not ``None``).
                #
                # ``TimeoutError`` is named explicitly as defense-in-depth:
                # ``AbrpClient.async_get_catalog`` already wraps a naked
                # ``asyncio.TimeoutError`` as ``AbrpApiError`` at the client
                # boundary, so under normal flow no TimeoutError reaches this
                # band. The explicit name guards against any future code path
                # that bypasses the wrapper — a regression there would
                # otherwise crash the entire refresh and freeze
                # ``self._catalog`` at ``None`` (force unbounded retry).
                _LOGGER.warning(
                    "ABRP catalog fetch failed; DeviceInfo.model will fall "
                    "back to the raw type code until the next integration "
                    "reload: %s",
                    err,
                )
                self._catalog = {}

        return [_enrich_with_catalog(raw, self._catalog) for raw in raw_vehicles]


def _parse_block_time(block: Mapping[str, Any]) -> datetime | None:
    """Return the block's ``time`` as a tz-aware datetime, or ``None``.

    Returns ``None`` whenever:

    * the block has no ``time`` key — defense; every keep-set block carries
      one in production but absence MUST NOT crash the staleness gate;
    * ``time`` is not a string — 14 existing test fixtures across the suite
      use opaque ``int`` markers (e.g. ``"time": 12345``) as placeholder
      values predating this gate. Returning ``None`` short-circuits the
      staleness comparison and lets the merge fall through to "adopt
      incoming", preserving the legacy contract those fixtures exercise;
    * the string is malformed — :func:`parse_datetime` returns ``None``
      via the regex-no-match branch at ``util/dt.py:215-218``;
    * the string is structurally well-formed but invalid (e.g.
      ``2026-13-01T00:00:00Z``, ``2026-02-30T...``) — :func:`parse_datetime`
      propagates :class:`ValueError` from the underlying
      :class:`datetime.datetime` constructor at ``util/dt.py:236``;
      caught here to keep the call-site branch-free;
    * the parsed datetime is naive (no tz suffix in the string) — naive
      vs. aware comparison would raise :class:`TypeError` at the
      staleness comparison site. ABRP's wire format always carries a
      ``Z`` suffix per the user-captured rollup sample (2026-05-25), so
      rejecting naive strings filters wire-shape regressions only.

    Defensive return-``None`` (rather than fail-loud) is load-bearing for
    the 14 existing fixtures named above; the docstring records the
    contract.
    """
    raw = block.get("time")
    if not isinstance(raw, str):
        return None
    try:
        parsed = parse_datetime(raw)
    except ValueError:
        return None
    if parsed is None or parsed.tzinfo is None:
        return None
    return parsed


class AbrpTelemetryCoordinator(
    TimestampDataUpdateCoordinator[dict[int, OutputPointWithVehicleId]]
):
    """Push-mode coordinator for the v2 ``/2/tlm`` SSE telemetry stream.

    Holds the current per-vehicle telemetry snapshot keyed by ``vehicleId``.
    Updates flow in from the SSE consumer task via :meth:`apply_frame`,
    which performs a partial-update merge (wire frames are deltas).
    ``update_interval`` is ``None`` because the
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
        # Value type is ``object | None`` so platforms whose presence
        # predicate returns a non-numeric signal (e.g. the device_tracker
        # platform's ``tuple[float, float]`` for GPS coordinates) share the
        # same registration surface as the scalar-returning sensors. The
        # only contract is "non-None == metric is present"; ``apply_frame``
        # discards the value after the None/non-None check.
        self._presence_predicates: dict[
            str, Callable[[Mapping[str, Any]], object | None]
        ] = {}
        self._presence_seen: set[tuple[int, str]] = set()
        # Per-vehicle, per-metric wall-clock of the most recent UNMERGED
        # frame in which the metric's value_fn returned non-None. Sensor's
        # ``extra_state_attributes`` surfaces this as ``last_reported_at``
        # so users can template against upstream freshness, not the
        # merge-preserved local snapshot. Stamped in :meth:`apply_frame`.
        self.last_reported_at: dict[int, dict[str, datetime]] = {}
        # Per-vehicle, per-metric upstream provider string from the most
        # recent UNMERGED frame that carried a usable provider for this
        # metric. Sticky on transient omission/malformed shape — see
        # :func:`_extract_provider` — so the user-visible attribute keeps
        # the last-known lineage rather than flashing absent on a frame
        # that observed the metric but omitted the provider claim. This
        # is the only intentional divergence from ``last_reported_at``,
        # which always overwrites with ``now`` whenever the metric is
        # present at all.
        self.last_provider: dict[int, dict[str, str]] = {}
        # SSE connection-state triage dict. Updated by ``_run_sse_loop`` at
        # the three loop transitions (open-stream / disconnect / before-sleep)
        # and surfaced verbatim by the diagnostics platform. Mutable in place
        # so the diagnostics call site reads a fresh snapshot via ``dict(...)``
        # copy without re-allocating the underlying object each transition.
        self.sse_state: dict[str, Any] = {
            "connected": False,
            "last_attempt_at": None,
            "last_connect_at": None,
            "last_disconnect_at": None,
            "last_disconnect_reason": None,
            "connect_count": 0,
            "current_backoff_seconds": 0,
        }

    @callback
    def forget_vehicle(self, vehicle_id: int) -> None:
        """Clear every per-vehicle surface for ``vehicle_id``.

        Wired to the stale-devices removal path in
        :func:`__init__._remove_stale_devices` so the in-memory state
        stays honest with the device registry. ``.pop(.., None)``
        semantics — calling for an unknown vid is a no-op so a vehicle
        that never surfaced a telemetry frame can still be removed
        without raising.

        Sweeps four surfaces: the merged telemetry snapshot, the
        per-metric ``last_reported_at`` and ``last_provider`` maps, and
        any ``(vehicle_id, *)`` entries in ``_presence_seen`` so a
        re-added vehicle re-fires its create-on-first-frame dispatch.
        ``async_set_updated_data`` is intentionally NOT invoked — there
        are no listeners interested in "vehicle disappeared from the
        merged state" beyond the stale-devices flow itself, which
        already removed the device + its entities.
        """
        self.data.pop(vehicle_id, None)
        self.last_reported_at.pop(vehicle_id, None)
        self.last_provider.pop(vehicle_id, None)
        self._presence_seen -= {
            pair for pair in self._presence_seen if pair[0] == vehicle_id
        }

    @callback
    def register_presence_predicates(
        self,
        predicates: Mapping[str, Callable[[Mapping[str, Any]], object | None]],
    ) -> None:
        """Register per-metric presence-evaluation callables (merge semantics).

        The sensor platform contributes its predicate keys; ``.update``
        merges them into a shared dict instead of clobbering. Re-registering
        the same key overwrites — by design, since a platform unload + reload
        cleanly replaces its own predicates without leaving stale entries
        behind.

        From the first call onwards :meth:`apply_frame` consults every
        registered predicate for each known metric and fires the
        dispatcher signal on the first non-None transition.
        """
        self._presence_predicates.update(predicates)

    @callback
    def mark_metric_seen(self, vehicle_id: int, metric_key: str) -> None:
        """Record a ``(vehicle_id, metric_key)`` pair as already-emitted.

        Called by the sensor platform for every entity it creates during the
        post-pre-warm inspection so the dispatcher does not double-fire when
        the next SSE frame carries the same metric.
        """
        self._presence_seen.add((vehicle_id, metric_key))

    async def async_seed_from_json_poll(
        self, vehicle_ids: list[int], session_token: str
    ) -> None:
        """Seed the per-vehicle telemetry map via one-shot ``GET /2/tlm/{id}`` calls.

        Best-effort: failures (transport / auth / per-vehicle permission)
        log and skip the affected vehicle rather than aborting setup. The
        SSE consumer subsequently overwrites stale seeds as frames arrive.

        Per-vehicle calls run in parallel via :func:`asyncio.gather` with
        ``return_exceptions=True`` so one vehicle's failure doesn't block
        the rest. Auth errors are NOT propagated to the global reauth
        flow from here — the SSE consumer (which also opens an
        authenticated stream) reaches the same 401 and triggers reauth
        via its existing path. Surfacing the auth failure from both sites
        would race two reauth flows.
        """
        if not vehicle_ids:
            return
        client = AbrpTelemetryClient(
            async_get_clientsession(self.hass), ABRP_APP_KEY, session_token
        )
        results = await asyncio.gather(
            *(client.async_get_one_shot(vid) for vid in vehicle_ids),
            return_exceptions=True,
        )
        for vehicle_id, result in zip(vehicle_ids, results, strict=True):
            if isinstance(result, AbrpAuthError):
                _LOGGER.warning(
                    "Telemetry seed for vehicle %d rejected (%s); SSE will retry auth",
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
            if isinstance(result, Exception):
                # Seed is best-effort. Log unexpected non-Abrp failures at
                # WARNING so they're visible without killing setup; SSE
                # remains the authoritative source and will rebuild the
                # per-vehicle map.
                _LOGGER.warning(
                    "Unexpected telemetry seed failure for vehicle %d: %s",
                    vehicle_id,
                    result,
                )
                continue
            if isinstance(result, BaseException):
                # ``Exception`` (not ``BaseException``) is the caught band so
                # ``asyncio.CancelledError`` / ``KeyboardInterrupt`` /
                # ``SystemExit`` propagate cleanly through unload / Ctrl-C
                # rather than being silently turned into "no seed for this
                # vehicle".
                raise result
            self.apply_frame({**result, "vehicleId": vehicle_id})

    @callback
    def apply_frame(self, frame: Mapping[str, Any]) -> None:
        """Merge one SSE frame into the per-vehicle telemetry map.

        The wire emits deltas — a frame that carries only ``power`` must
        not zero out a previously-received ``soc``. Shallow-overlay merge
        keeps unchanged metrics intact while updating the ones present.

        Null leaves in a frame are treated as "no update for this metric
        in this delta" — i.e. equivalent to the key being omitted entirely.
        Top-level null values, dicts with all-null leaves, and empty dicts
        are all skipped; mixed-null inner dicts deep-merge the non-null
        leaves over the prior good values.

        After merging, fires :func:`signal_new_metric` once per
        ``(vehicle_id, metric_key)`` pair whose presence predicate first
        evaluates to non-None — the sensor platform listens on this signal
        to lazily create the corresponding entity.

        During the pre-warm window (before the sensor platform has
        registered predicates) ``_presence_predicates`` is empty and the
        per-predicate loop short-circuits. This is deliberate: frames
        accumulated during pre-warm are picked up by the platform's direct
        inspection of ``self.data`` after the window closes — predicate
        registration BEFORE the first post-setup frame guarantees no
        first-arrival is lost.
        """
        vehicle_id = frame["vehicleId"]
        merged: dict[str, Any] = dict(self.data.get(vehicle_id, {}))
        # Per-block staleness pre-scan: identify wire keys whose incoming
        # block carries an ISO ``time`` strictly older than the stored
        # block's ``time``. Both ``time``s must parse to tz-aware
        # datetimes (see :func:`_parse_block_time`) — any non-string /
        # malformed / naive / absent ``time`` on either side falls
        # through and the merge adopts incoming. Built BEFORE the merge
        # mutates ``merged`` so the comparison reads the prior stored
        # state, not the in-progress overlay. The presence-predicate
        # dispatch loop below iterates against ``merged_frame``, which
        # retains prior fresh values where stale was skipped — no
        # spurious first-observation dispatch with a 20h-old value.
        #
        # ``stale_keys`` is WIRE-KEYED (camelCase for the 4 asymmetric
        # metrics — see ``SENSOR_VALUE_FNS``): we populate it from
        # ``frame.items()`` so the membership check at the stamp loop
        # below MUST also compare against ``wire_key``, not the
        # snake_case registry ``key``. The loop variable is named
        # ``wire_key`` here (and in the merge loop) to make that
        # namespace visually distinct at every line-of-use; the stamp
        # loop carries both names and the explicit comment.
        stale_keys: set[str] = set()
        for wire_key, value in frame.items():
            if not isinstance(value, dict):
                continue
            incoming_time = _parse_block_time(value)
            if incoming_time is None:
                continue
            existing = merged.get(wire_key)
            if not isinstance(existing, dict):
                continue
            stored_time = _parse_block_time(existing)
            if stored_time is None:
                continue
            if incoming_time < stored_time:
                stale_keys.add(wire_key)
        for wire_key, value in frame.items():
            if wire_key in stale_keys:
                continue
            if value is None:
                continue
            if isinstance(value, dict):
                inner = {ik: iv for ik, iv in value.items() if iv is not None}
                if not inner:
                    continue
                existing = merged.get(wire_key)
                if isinstance(existing, dict):
                    merged[wire_key] = {**existing, **inner}
                else:
                    # The wire is consistent per metric (dict-vs-scalar shape
                    # doesn't change mid-stream); a scalar ``existing`` here
                    # would be a contract violation by the upstream, so we
                    # drop the scalar and adopt the new inner dict rather
                    # than attempt a structural merge.
                    merged[wire_key] = inner
            else:
                merged[wire_key] = value
        merged_frame = cast(OutputPointWithVehicleId, merged)
        now = utcnow()
        # Stamp per-key against the UNMERGED ``frame`` (not the merged
        # state). The merge preserves prior values across silent frames
        # so a frame that omits voltage would still expose voltage in
        # ``merged_frame``; stamping off the merged state would defeat
        # the user-visible contract of ``last_reported_at`` ("when did
        # upstream last surface this field"). Pinned by the trajectory
        # tests in test_restore.py.
        # ``STAMPED_VALUE_FNS`` is module-level concat populated at import
        # time so frames arriving during the pre-warm window stamp correctly.
        for key, wire_key, value_fn in STAMPED_VALUE_FNS:
            # ``stale_keys`` is WIRE-KEYED (see pre-scan comment above);
            # the four asymmetric metrics (``calibrated_ref_cons``,
            # ``battery_capacity``, ``range``, ``battery_temperature``)
            # have ``key != wire_key``, so the snake_case registry
            # ``key`` would silently miss the stale-skip and stamp an
            # older rollup. Compare against ``wire_key``.
            if wire_key in stale_keys:
                continue
            if value_fn(frame) is not None:
                # ``last_reported_at`` has a SINGLE gate: the metric
                # was observed in this unmerged frame AND not
                # stale-skipped. Stale-skip preserves the prior fresher
                # stamp — otherwise an older rollup would overwrite the
                # user-visible "when did upstream last surface this
                # field" timestamp with a backdated one. Always
                # overwrite otherwise.
                self.last_reported_at.setdefault(vehicle_id, {})[key] = now
                # ``key`` is the registry / entity-description key
                # (snake_case); ``wire_key`` is what the value_fn reads
                # from the raw frame (camelCase for four fields — see
                # ``SENSOR_VALUE_FNS``). The stamp dicts use the
                # registry key everywhere so the entity surface and
                # diagnostics align with the sensor unique_id.
                provider = _extract_provider(frame, wire_key)
                # ``last_provider`` is DOUBLE-gated: outer (above) +
                # inner (provider is not None). Asymmetric vs
                # ``last_reported_at`` is intentional sticky-on-omission:
                # a metric block present without a usable provider
                # (absent / non-string / empty/whitespace-only) RETAINS
                # the prior value rather than blanking it. Provider
                # rarely flips mid-stream; transient absence shouldn't
                # blank the user-visible signal. Single contract — same
                # reject set on the wire boundary (here) and the
                # recorder boundary (sensor + tracker
                # ``async_added_to_hass``).
                if provider is not None:
                    self.last_provider.setdefault(vehicle_id, {})[key] = provider
        self.async_set_updated_data({**self.data, vehicle_id: merged_frame})
        # ``async_set_updated_data`` does not invoke ``_async_refresh_finished``
        # (only the polling path does), so the framework-provided timestamp
        # would stay ``None`` for this push coordinator. Stamp explicitly so
        # diagnostics' "last_update_success_time" reads as "time of last
        # applied SSE frame" — the highest-value SSE triage signal.
        self.last_update_success_time = now

        if not self._presence_predicates:
            return
        signal = signal_new_metric(self.config_entry.entry_id)
        for metric_key, predicate in self._presence_predicates.items():
            if (vehicle_id, metric_key) in self._presence_seen:
                continue
            try:
                value = predicate(merged_frame)
            except Exception:
                _LOGGER.exception(
                    "Presence predicate %r raised for vehicle %d; skipping dispatch",
                    metric_key,
                    vehicle_id,
                )
                continue
            if value is None:
                continue
            async_dispatcher_send(self.hass, signal, vehicle_id, metric_key)


async def _run_sse_loop(
    hass: HomeAssistant,
    entry: AbetterrouteplannerConfigEntry,
    coordinator: AbrpTelemetryCoordinator,
    session: OAuth2Session,
    vehicle_ids: list[int],
) -> None:
    """Long-lived consumer that streams v2 telemetry into the coordinator.

    Reconnects with exponential backoff (:data:`_SSE_BACKOFF_SECONDS`,
    capped at the last value) on transient failures. Resets to the first
    delay after any successful frame is received from a connection.

    Before each reconnect attempt the OAuth token is refreshed via
    ``session.async_ensure_token_valid()``; a transparent refresh prevents
    a spurious 401 → reauth cycle once the (~1h) access_token lapses. Only
    a 4xx from the refresh itself (revoked / rotated refresh token) or an
    :exc:`AbrpAuthError` from the stream surfaces as
    :class:`ConfigEntryAuthFailed`. All other transport failures fall
    through to the backoff path.

    Stall detection lives at this layer, not in the aiohttp request: each
    ``__anext__()`` on the SSE async iterator is wrapped in
    :func:`asyncio.wait_for` with a :data:`_SSE_FRAME_WATCHDOG_SECONDS`
    bound. A half-open TCP / NAT-rebind / cell-modem-suspend that the
    kernel never sees a FIN for would otherwise park the consumer
    indefinitely (production stall shape — user-reported 16 h flatline).
    On timeout the inner await is cancelled, ``agen.aclose()`` releases
    the underlying aiohttp response in the ``finally`` block, the outer
    handler stamps ``last_disconnect_reason="watchdog_stall_{N}s"`` and
    the loop reconnects after the standard backoff.

    The server's natural ~200 s idle close (probe-confirmed) surfaces as
    ``ClientPayloadError`` → ``AbrpApiError`` → reconnect with the
    first-tier backoff (5 s); successful frames reset ``delay_idx`` so
    the cycle stays at 5 s and does not escalate.

    Two cancellation paths are supported on entry unload: (a) naked
    propagation — ``wait_for`` delivers ``CancelledError`` into the
    generator's frame, ``aclose()`` cleans up, the exception propagates
    out of this function; (b) fixture- or future-parser-masked — an
    iterator that catches ``CancelledError`` inside ``__anext__`` and
    re-raises as ``StopAsyncIteration`` would let the loop fall through
    to the backoff sleep with the cancel signal "consumed". The retained
    :meth:`asyncio.Task.cancelling` check below catches that case.
    """
    delay_idx = 0
    while True:
        # Stamp every connect-cycle attempt — including ones where the
        # pre-stream token refresh fails — so diagnostics' ``last_attempt_at``
        # reflects "loop is actively retrying" during an IdP outage instead
        # of freezing at the last successful refresh. Without this, a
        # consumer spinning on transient ``ClientResponseError`` /
        # ``ClientError`` reads as stale in diagnostics and triage assumes
        # the loop is wedged.
        coordinator.sse_state["last_attempt_at"] = utcnow().isoformat()
        try:
            await session.async_ensure_token_valid()
        except ClientResponseError as err:
            if HTTPStatus.BAD_REQUEST <= err.status < HTTPStatus.INTERNAL_SERVER_ERROR:
                coordinator.async_set_update_error(
                    ConfigEntryAuthFailed(
                        translation_domain=DOMAIN,
                        translation_key="oauth2_session_not_valid",
                    )
                )
                _LOGGER.warning(
                    "OAuth refresh rejected (HTTP %s); triggering reauth", err.status
                )
                entry.async_start_reauth(hass)
                return
            _LOGGER.debug(
                "Transient OAuth refresh failure (HTTP %s); backing off", err.status
            )
        except ClientError as err:
            _LOGGER.debug("Transient OAuth refresh failure (%s); backing off", err)
        else:
            client = AbrpTelemetryClient(
                async_get_clientsession(hass),
                ABRP_APP_KEY,
                session.token["access_token"],
            )
            coordinator.sse_state["current_backoff_seconds"] = 0
            disconnect_reason: str | None = "stream_closed"
            saw_frame = False
            # ``client.stream(...)`` is an async-generator factory — the
            # call returns an :class:`AsyncGenerator` that carries
            # ``aclose()`` for the ``finally`` cleanup below. Test fixtures
            # (``_FrameStream`` / ``_BlockNaked``) provide a matching no-op
            # ``aclose`` so iteration semantics match the production shape.
            agen: AsyncGenerator[OutputPointWithVehicleId] | None = None
            try:
                try:
                    agen = client.stream(vehicle_ids)
                    while True:
                        try:
                            frame = await asyncio.wait_for(
                                anext(agen),
                                timeout=_SSE_FRAME_WATCHDOG_SECONDS,
                            )
                        except StopAsyncIteration:
                            break
                        if not saw_frame:
                            coordinator.sse_state["connected"] = True
                            coordinator.sse_state["last_connect_at"] = (
                                utcnow().isoformat()
                            )
                            coordinator.sse_state["connect_count"] += 1
                            saw_frame = True
                        coordinator.apply_frame(frame)
                        delay_idx = 0
                except AbrpAuthError as err:
                    disconnect_reason = _summarize_exc(err)
                    if saw_frame:
                        coordinator.sse_state["connected"] = False
                        coordinator.sse_state["last_disconnect_at"] = (
                            utcnow().isoformat()
                        )
                    coordinator.sse_state["last_disconnect_reason"] = disconnect_reason
                    coordinator.async_set_update_error(
                        ConfigEntryAuthFailed(
                            translation_domain=DOMAIN,
                            translation_key="abrp_session_invalid",
                        )
                    )
                    _LOGGER.warning(
                        "SSE stream rejected (%s); triggering reauth and exiting task",
                        err,
                    )
                    entry.async_start_reauth(hass)
                    return
                except TimeoutError:
                    disconnect_reason = f"watchdog_stall_{_SSE_FRAME_WATCHDOG_SECONDS}s"
                    _LOGGER.debug(
                        "SSE stream stalled (no frames for %ss); forcing reconnect",
                        _SSE_FRAME_WATCHDOG_SECONDS,
                    )
                except AbrpApiError as err:
                    disconnect_reason = _summarize_exc(err)
                    _LOGGER.debug("SSE stream disconnected (%s); reconnecting", err)
            finally:
                # Release the underlying aiohttp response even if the
                # watchdog fires mid-iteration or an exception aborts the
                # loop. ``aclose()`` is idempotent and tolerates an
                # already-finished generator. ``agen`` stays ``None`` if
                # ``client.stream(...)`` itself raised before assignment
                # (e.g. a mock with ``side_effect=AbrpApiError`` in tests,
                # or a pre-headers transport failure in production).
                #
                # The ``except Exception`` guard around ``aclose()`` is a
                # belt for the case where ``response.__aexit__()`` raises a
                # ``ClientError`` while tearing down a half-broken socket:
                # without it, the exception escapes ``_run_sse_loop``, the
                # background task dies, and the consumer never reconnects.
                # Log + swallow so the outer ``while True:`` continues into
                # the standard backoff path.
                if agen is not None:
                    try:
                        await agen.aclose()
                    except Exception:  # noqa: BLE001 - keep the reconnect loop alive
                        _LOGGER.warning(
                            "SSE generator aclose() raised; continuing reconnect loop",
                            exc_info=True,
                        )

            if saw_frame:
                coordinator.sse_state["connected"] = False
                coordinator.sse_state["last_disconnect_at"] = utcnow().isoformat()
            coordinator.sse_state["last_disconnect_reason"] = disconnect_reason

        # The ``finally: aclose()`` above handles the naked-cancellation
        # path. The check here covers the fixture- or future-parser-masked
        # path: an iterator that catches ``CancelledError`` and re-raises
        # as ``StopAsyncIteration`` would let the wait_for loop exit
        # cleanly via the StopAsyncIteration branch, ``aclose()`` no-ops,
        # and execution falls through to ``asyncio.sleep(delay)`` with the
        # pending cancellation "consumed". Bailing here turns it back into
        # a clean return so unload finishes promptly.
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            return

        delay = _SSE_BACKOFF_SECONDS[min(delay_idx, len(_SSE_BACKOFF_SECONDS) - 1)]
        coordinator.sse_state["current_backoff_seconds"] = delay
        await asyncio.sleep(delay)
        delay_idx = min(delay_idx + 1, len(_SSE_BACKOFF_SECONDS) - 1)
