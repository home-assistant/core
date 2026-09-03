"""Tests for the thin push telemetry coordinator's HA-side policy."""

from datetime import UTC, datetime
import logging
from unittest.mock import patch

from aioabrp import ConnectionEvent, ConnectionState, Metric, Telemetry
import pytest

from homeassistant.components.abetterrouteplanner.coordinator import (
    AbrpTelemetryCoordinator,
)
from homeassistant.core import HomeAssistant, callback

from .conftest import MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2, build_metric_value

from tests.common import MockConfigEntry


@pytest.fixture(name="telemetry_coordinator")
def telemetry_coordinator_fixture(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
) -> AbrpTelemetryCoordinator:
    """A thin telemetry coordinator bound to a real (added) config entry."""
    config_entry_with_vehicles.add_to_hass(hass)
    return AbrpTelemetryCoordinator(hass, config_entry_with_vehicles)


async def test_provider_set_then_sticky_on_omission_then_updated(
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Provider stickiness: set → retained on omission → updated on new value."""
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
    """Provider stamps are independent per ``(vehicle, metric)`` pair."""
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
    """``last_reported_at`` is stamped at apply (RECEIPT) time, ignoring mv.time."""
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


async def test_auth_failed_connection_event_logs_warning(
    hass: HomeAssistant,
    telemetry_coordinator: AbrpTelemetryCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An ``AUTH_FAILED`` connection event logs a warning and starts no flow."""
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
    """DISCONNECTED only logs; CONNECTED bumps ``connect_count``."""
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
    """Repeated identical connection states log only on the transition."""
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
    assert coordinator.last_connection_event is not None
    assert coordinator.last_connection_event.state is ConnectionState.CONNECTED


class _FatalSignal(BaseException):
    """A non-``Exception`` ``BaseException`` stand-in for fatal control signals."""


async def test_terminal_auth_failure_sets_and_clears_stream_auth_failed(
    hass: HomeAssistant,
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """AUTH_FAILED latches the terminal flag; only a reconnect clears it.

    aioabrp returns from its run loop once it has dispatched ``AUTH_FAILED``,
    so the later events driven here cannot occur today. They pin the latch's
    own state machine against a future library that does emit them.
    """
    coordinator = telemetry_coordinator

    assert coordinator.stream_auth_failed is False

    coordinator.on_connection_change(
        ConnectionEvent(ConnectionState.AUTH_FAILED, "401")
    )
    await hass.async_block_till_done()
    assert coordinator.stream_auth_failed is True

    coordinator.on_connection_change(
        ConnectionEvent(ConnectionState.DISCONNECTED, "idle close")
    )
    await hass.async_block_till_done()
    assert coordinator.stream_auth_failed is True

    coordinator.on_connection_change(ConnectionEvent(ConnectionState.CONNECTED))
    await hass.async_block_till_done()
    assert coordinator.stream_auth_failed is False


async def test_terminal_auth_failure_notifies_listeners(
    hass: HomeAssistant,
    telemetry_coordinator: AbrpTelemetryCoordinator,
) -> None:
    """Entities are told to re-evaluate availability on the terminal failure."""
    coordinator = telemetry_coordinator
    notified = 0

    @callback
    def _listener() -> None:
        nonlocal notified
        notified += 1

    coordinator.async_add_listener(_listener)

    coordinator.on_connection_change(
        ConnectionEvent(ConnectionState.AUTH_FAILED, "401")
    )
    await hass.async_block_till_done()
    assert notified == 1

    # Latched: a repeat of the same terminal state is not a fresh transition.
    coordinator.on_connection_change(
        ConnectionEvent(ConnectionState.AUTH_FAILED, "401")
    )
    await hass.async_block_till_done()
    assert notified == 1
