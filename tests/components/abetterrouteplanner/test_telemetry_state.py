"""Tests for the thin push telemetry coordinator's HA-side policy.

The :class:`aioabrp.TelemetryStream` owns all wire parsing, frame merging,
monotonicity and reconnect machinery; those are covered in the library. What
remains HA-side — and is pinned here — is the policy
:class:`AbrpTelemetryCoordinator` layers on top of the typed metric batches
the stream hands it:

* provider stickiness on omission;
* ``last_reported_at`` stamped at RECEIPT time (not the wire ``time``);
* first-appearance ``signal_new_metric`` dispatch (presence);
* ``AUTH_FAILED`` → warning log (and the no-op connection states);
* once-per-transition connection logging;
* ``async_seed`` per-vehicle failure tolerance.

These drive the real coordinator code paths directly — either via
``on_update`` / ``on_connection_change`` (the same callbacks the stream
invokes) or via the ``fake_stream`` driver — never by re-implementing the
policy in the test.
"""

from datetime import UTC, datetime
import logging
from unittest.mock import AsyncMock, patch

from aioabrp import (
    AbrpApiError,
    AbrpAuthError,
    AbrpClient,
    ConnectionEvent,
    ConnectionState,
    Metric,
    Telemetry,
)
import pytest

from homeassistant.components.abetterrouteplanner.const import signal_new_metric
from homeassistant.components.abetterrouteplanner.coordinator import (
    AbrpTelemetryCoordinator,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .conftest import MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2, build_metric_value

from tests.common import MockConfigEntry


@pytest.fixture(name="telemetry_coordinator")
def telemetry_coordinator_fixture(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
) -> AbrpTelemetryCoordinator:
    """A thin telemetry coordinator bound to a real (added) config entry.

    The entry is added to hass so ``async_dispatcher_send`` (entry-scoped
    signal) operates against a real entry. The coordinator is constructed
    directly — the same object the
    integration builds — and driven via its ``on_update`` /
    ``on_connection_change`` / ``async_seed`` callbacks.
    """
    config_entry_with_vehicles.add_to_hass(hass)
    return AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)


async def test_provider_set_then_sticky_on_omission_then_updated(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Provider stickiness: set → retained on omission → updated on new value.

    A frame carrying a provider stamps ``last_provider``; a later frame for
    the same metric whose ``MetricValue.provider`` is ``None`` RETAINS the
    prior provider (sticky-on-omission — transient absence shouldn't blank
    the user-visible signal); a frame carrying a fresh provider overwrites.
    """
    coordinator = telemetry_coordinator

    coordinator.on_update(
        MOCK_VEHICLE_ID,
        Telemetry(voltage=build_metric_value(400.0, provider="RIVIAN_STREAM")),
    )
    assert coordinator.last_provider[MOCK_VEHICLE_ID][Metric.VOLTAGE] == "RIVIAN_STREAM"

    # provider=None: the metric is present but carries no provider — retain.
    coordinator.on_update(
        MOCK_VEHICLE_ID,
        Telemetry(voltage=build_metric_value(420.0, provider=None)),
    )
    assert coordinator.last_provider[MOCK_VEHICLE_ID][Metric.VOLTAGE] == "RIVIAN_STREAM"

    # A fresh provider wins — last-frame semantics.
    coordinator.on_update(
        MOCK_VEHICLE_ID,
        Telemetry(voltage=build_metric_value(420.0, provider="APP_LOCATION")),
    )
    assert coordinator.last_provider[MOCK_VEHICLE_ID][Metric.VOLTAGE] == "APP_LOCATION"


async def test_provider_isolated_per_vehicle_and_metric(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Provider stamps are independent per ``(vehicle, metric)`` pair.

    A single frame reporting two metrics from two upstreams stamps each
    independently; a second vehicle's stamp never bleeds into the first.
    """
    coordinator = telemetry_coordinator

    coordinator.on_update(
        MOCK_VEHICLE_ID,
        Telemetry(
            soc=build_metric_value(0.85, provider="TESLA_FLEET_STREAM"),
            odometer=build_metric_value(100000.0, provider="APP_LOCATION"),
        ),
    )
    coordinator.on_update(
        MOCK_VEHICLE_ID_2,
        Telemetry(voltage=build_metric_value(380.0, provider="RIVIAN_STREAM")),
    )

    assert coordinator.last_provider[MOCK_VEHICLE_ID][Metric.SOC] == (
        "TESLA_FLEET_STREAM"
    )
    assert coordinator.last_provider[MOCK_VEHICLE_ID][Metric.ODOMETER] == "APP_LOCATION"
    assert coordinator.last_provider[MOCK_VEHICLE_ID_2][Metric.VOLTAGE] == (
        "RIVIAN_STREAM"
    )
    assert Metric.VOLTAGE not in coordinator.last_provider[MOCK_VEHICLE_ID]


async def test_last_reported_at_is_receipt_time_not_wire_time(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """``last_reported_at`` is stamped at apply (RECEIPT) time, ignoring mv.time.

    Policy: ``last_reported_at`` answers "when did HA last see this field",
    NOT "what measurement-time did upstream attach". The ``MetricValue.time``
    here is a deliberately different, older instant; the stamp must equal the
    patched ``dt_util.utcnow()`` receipt instant, never ``mv.time``.
    """
    coordinator = telemetry_coordinator

    receipt = datetime(2026, 6, 11, 12, 30, 0, tzinfo=UTC)
    wire_time = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)

    with patch(
        "homeassistant.components.abetterrouteplanner.coordinator.dt_util.utcnow",
        return_value=receipt,
    ):
        coordinator.on_update(
            MOCK_VEHICLE_ID,
            Telemetry(soc=build_metric_value(0.5, time=wire_time)),
        )

    stamp = coordinator.last_reported_at[MOCK_VEHICLE_ID][Metric.SOC]
    assert stamp == receipt
    assert stamp != wire_time


async def test_presence_dispatch_fires_on_first_seen_for_registered_metrics(
    hass: HomeAssistant,
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """``signal_new_metric`` fires per first-seen ``(vid, Metric)`` pair.

    Only metrics in the registered presence set dispatch; a metric outside
    the registered set never dispatches. The first-appearance dispatch fires
    while ``(vid, Metric)`` is not yet in ``_presence_seen``; the production
    sensor platform's listener calls :meth:`mark_metric_seen` after creating
    the entity — simulated here — so a subsequent frame does not re-fire.
    """
    coordinator = telemetry_coordinator
    coordinator.register_presence_predicates({Metric.SOC})

    signal = signal_new_metric(coordinator.config_entry.entry_id)
    dispatched: list[tuple[int, Metric]] = []

    @callback
    def _record(vehicle_id: int, metric: Metric) -> None:
        dispatched.append((vehicle_id, metric))

    unsub = async_dispatcher_connect(hass, signal, _record)
    try:
        # First appearance of a registered metric → one dispatch.
        coordinator.on_update(MOCK_VEHICLE_ID, Telemetry(soc=build_metric_value(0.5)))
        # A metric NOT in the presence set → no dispatch.
        coordinator.on_update(
            MOCK_VEHICLE_ID, Telemetry(voltage=build_metric_value(400.0))
        )
        await hass.async_block_till_done()
        assert dispatched == [(MOCK_VEHICLE_ID, Metric.SOC)]

        # The sensor platform marks the pair seen after creating the entity;
        # a later frame for the same pair must not re-fire the signal.
        coordinator.mark_metric_seen(MOCK_VEHICLE_ID, Metric.SOC)
        coordinator.on_update(MOCK_VEHICLE_ID, Telemetry(soc=build_metric_value(0.6)))
        await hass.async_block_till_done()
        assert dispatched == [(MOCK_VEHICLE_ID, Metric.SOC)]
    finally:
        unsub()


async def test_mark_metric_seen_suppresses_dispatch(
    hass: HomeAssistant,
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """``mark_metric_seen`` pre-marks a pair so the next frame does not dispatch.

    The sensor platform calls ``mark_metric_seen`` for entities it creates
    during the setup-time seed inspection so the dispatcher does not double-fire
    when the next frame carries the same metric.
    """
    coordinator = telemetry_coordinator
    coordinator.register_presence_predicates({Metric.SOC})

    signal = signal_new_metric(coordinator.config_entry.entry_id)
    dispatched: list[tuple[int, Metric]] = []

    @callback
    def _record(vehicle_id: int, metric: Metric) -> None:
        dispatched.append((vehicle_id, metric))

    unsub = async_dispatcher_connect(hass, signal, _record)
    try:
        coordinator.mark_metric_seen(MOCK_VEHICLE_ID, Metric.SOC)
        coordinator.on_update(MOCK_VEHICLE_ID, Telemetry(soc=build_metric_value(0.5)))
        await hass.async_block_till_done()

        assert dispatched == []
    finally:
        unsub()


async def test_auth_failed_connection_event_logs_warning(
    hass: HomeAssistant,
    telemetry_coordinator: AbrpTelemetryCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An ``AUTH_FAILED`` connection event logs a warning and starts no flow.

    Reauth is split into a follow-up, so the connection callback only logs the
    auth failure. The garage coordinator is the authoritative auth-failure
    signal, so AUTH_FAILED must not itself start any config flow.
    """
    coordinator = telemetry_coordinator

    with caplog.at_level(
        logging.WARNING,
        logger="homeassistant.components.abetterrouteplanner.coordinator",
    ):
        coordinator.on_connection_change(
            ConnectionEvent(ConnectionState.AUTH_FAILED, "401")
        )
        await hass.async_block_till_done()

    assert "auth failed" in caplog.text.lower()
    assert not hass.config_entries.flow.async_progress()


async def test_disconnected_only_logs_and_connected_bumps_count(
    hass: HomeAssistant,
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """DISCONNECTED only logs; CONNECTED bumps ``connect_count``.

    Availability is value-based and deliberately ignores connection state —
    the ABRP server closes idle streams as steady-state, so a DISCONNECTED
    event must never start a config flow. CONNECTED increments the in-memory
    triage counter.
    """
    coordinator = telemetry_coordinator

    assert coordinator.connect_count == 0

    coordinator.on_connection_change(
        ConnectionEvent(ConnectionState.DISCONNECTED, "idle close")
    )
    coordinator.on_connection_change(ConnectionEvent(ConnectionState.CONNECTED))
    await hass.async_block_till_done()

    assert coordinator.connect_count == 1
    assert not hass.config_entries.flow.async_progress()


async def test_connection_logging_is_once_per_transition(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Repeated identical connection states log only on the transition.

    Two consecutive DISCONNECTED events log once (the state didn't change on
    the second); a following CONNECTED is a fresh transition and logs again.
    ``last_connection_event`` always tracks the most recent event regardless
    of whether it logged.
    """
    coordinator = telemetry_coordinator

    with caplog.at_level(
        logging.INFO,
        logger="homeassistant.components.abetterrouteplanner.coordinator",
    ):
        coordinator.on_connection_change(
            ConnectionEvent(ConnectionState.DISCONNECTED, "first")
        )
        coordinator.on_connection_change(
            ConnectionEvent(ConnectionState.DISCONNECTED, "second")
        )
        coordinator.on_connection_change(ConnectionEvent(ConnectionState.CONNECTED))

    disconnect_logs = [
        record for record in caplog.records if "disconnected" in record.message.lower()
    ]
    connect_logs = [
        record
        for record in caplog.records
        if "connected" in record.message.lower()
        and "disconnected" not in record.message.lower()
    ]
    assert len(disconnect_logs) == 1
    assert len(connect_logs) == 1
    # The most recent event is always recorded even when it didn't log.
    assert coordinator.last_connection_event is not None
    assert coordinator.last_connection_event.state is ConnectionState.CONNECTED


class _FatalSignal(BaseException):
    """A non-``Exception`` ``BaseException`` stand-in for fatal control signals.

    Models the ``CancelledError`` / ``KeyboardInterrupt`` / ``SystemExit``
    family ``async_seed`` must re-raise rather than swallow, without using a
    concrete type pytest / asyncio special-case.
    """


@pytest.mark.parametrize(
    "swallowed_error",
    [
        pytest.param(AbrpAuthError("invalid session"), id="auth_error"),
        pytest.param(AbrpApiError("backend overloaded"), id="api_error"),
    ],
)
async def test_async_seed_swallows_abrp_errors_for_one_vehicle(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    mock_abrp_client: AsyncMock,
    swallowed_error: Exception,
) -> None:
    """An Abrp auth/api failure for one vehicle is swallowed; others still seed.

    ``async_get_current_telemetry`` raising for one vehicle (auth or api) is
    logged-and-skipped — that vid is absent from ``data`` while the healthy
    vehicle is applied. Auth failures are NOT escalated from the seed path (the
    garage coordinator is the authoritative auth-failure signal).
    """
    coordinator = telemetry_coordinator

    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = Telemetry(
        soc=build_metric_value(0.42)
    )
    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID_2] = swallowed_error

    # ``async_get_current_telemetry`` is patched on the class by
    # ``mock_abrp_client``, so a bare uninitialised instance suffices to drive
    # the seed path.
    client = AbrpClient.__new__(AbrpClient)

    await coordinator.async_seed(client, [MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2])

    assert coordinator.data[MOCK_VEHICLE_ID].soc is not None
    assert coordinator.data[MOCK_VEHICLE_ID].soc.value == 0.42
    assert MOCK_VEHICLE_ID_2 not in coordinator.data


async def test_async_seed_reraises_non_abrp_base_exception(
    telemetry_coordinator: AbrpTelemetryCoordinator,
    mock_abrp_client: AsyncMock,
) -> None:
    """A non-Abrp ``BaseException`` from a seed call re-raises (not swallowed).

    ``async_seed`` swallows only ``AbrpAuthError`` / ``AbrpApiError``; a
    generic ``Exception`` is logged-and-skipped but a non-``Exception``
    ``BaseException`` propagates so cancellation / interpreter-shutdown
    signals are never silently turned into "no seed for this vehicle".

    A bespoke ``BaseException`` subclass stands in for the
    ``CancelledError`` / ``KeyboardInterrupt`` / ``SystemExit`` family the
    code path guards against, without tripping pytest's special handling of
    those concrete types.
    """
    coordinator = telemetry_coordinator

    mock_abrp_client.seed_responses[MOCK_VEHICLE_ID] = _FatalSignal()

    client = AbrpClient.__new__(AbrpClient)

    with pytest.raises(_FatalSignal):
        await coordinator.async_seed(client, [MOCK_VEHICLE_ID])
