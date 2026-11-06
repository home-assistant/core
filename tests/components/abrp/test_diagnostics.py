"""Tests for the A Better Routeplanner diagnostics."""

from datetime import UTC, datetime
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from aioabrp import (
    ChargingState,
    ConnectionEvent,
    ConnectionState,
    Location,
    MetricValue,
    Telemetry,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_MODEL,
    MOCK_VEHICLE_NAME,
    SENSOR_TEST_SUB,
    USER_SUB,
    build_vehicle_model_display,
    fire_connection,
    fire_frame,
)

# Far future, so setup never refreshes the token and the snapshot stays stable.
_EXPIRES_AT = 4102444800.0
_LOCATION = Location(lat=59.3293, lon=18.0686)
_ELEVATION = 35.0
# aiohttp timeouts quote the stream URL, which lists the subscribed vehicle ids.
_TIMEOUT = ConnectionEvent(
    ConnectionState.DISCONNECTED,
    "AbrpApiError: Connection timeout to host "
    f"https://api.iternio.com/2/tlm?vehicleIds={MOCK_VEHICLE_ID}",
)


def _metric_value[T](value: T) -> MetricValue[T]:
    """Build a metric value with a pinned time and provider."""
    return MetricValue(
        value=value, time=datetime(2026, 11, 4, 7, tzinfo=UTC), provider="RIVIAN_STREAM"
    )


_FRAME = (
    MOCK_VEHICLE_ID,
    Telemetry(
        soc=_metric_value(85.0),
        charging_state=_metric_value(ChargingState.CHARGING_AC),
        location=_metric_value(_LOCATION),
        elevation=_metric_value(_ELEVATION),
    ),
)


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Pin the OAuth token expiry."""
    return _EXPIRES_AT


@pytest.fixture(autouse=True)
async def setup_entry(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_abrp_client: AsyncMock,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Set up the integration; only the first vehicle resolves a display."""
    mock_abrp_client.display_responses[MOCK_VEHICLE_MODEL] = (
        build_vehicle_model_display()
    )
    await setup_integration(hass, config_entry_with_vehicles)


async def _replay(hass: HomeAssistant, mock_telemetry_stream: MagicMock) -> None:
    """Deliver a timeout and a telemetry frame through the stream."""
    fire_connection(mock_telemetry_stream, _TIMEOUT)
    fire_frame(mock_telemetry_stream, *_FRAME)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("events", "expected"),
    [
        pytest.param(
            [], {"state": None, "reason": None, "auth_failed": False}, id="no_event"
        ),
        pytest.param(
            [ConnectionEvent(ConnectionState.AUTH_FAILED, "HTTP 401")],
            {"state": "auth_failed", "reason": "HTTP 401", "auth_failed": True},
            id="auth_failed",
        ),
    ],
)
async def test_stream_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    events: list[ConnectionEvent],
    expected: dict[str, Any],
) -> None:
    """The stream block reports the last connection event and auth failure."""
    for event in events:
        fire_connection(mock_telemetry_stream, event)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_with_vehicles
    )
    assert diagnostics["stream"] == expected


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Diagnostics show the entry, stream state and per-vehicle metrics."""
    await _replay(hass, mock_telemetry_stream)

    assert (
        await get_diagnostics_for_config_entry(
            hass, hass_client, config_entry_with_vehicles
        )
        == snapshot
    )


async def test_diagnostics_omits_personal_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_with_vehicles: MockConfigEntry,
    token_entry: dict[str, Any],
    mock_telemetry_stream: MagicMock,
) -> None:
    """No secret, account id, vehicle identity or position reaches the dump."""
    await _replay(hass, mock_telemetry_stream)
    dumped = json.dumps(
        await get_diagnostics_for_config_entry(
            hass, hass_client, config_entry_with_vehicles
        )
    )

    # USER_SUB is only inside the id_token, so it would leak if claims were decoded.
    leaks = (
        SENSOR_TEST_SUB,
        USER_SUB,
        token_entry["access_token"],
        token_entry["refresh_token"],
        token_entry["id_token"],
        MOCK_VEHICLE_NAME,
        str(MOCK_VEHICLE_ID),
        str(_LOCATION.lat),
        str(_LOCATION.lon),
        str(_ELEVATION),
    )
    assert [leak for leak in leaks if leak in dumped] == []
