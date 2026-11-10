"""Tests for the sensor platform of the Pterodactyl integration."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientConnectionError, ClientError, ClientResponseError
from freezegun.api import FrozenDateTimeFactory
from pydactyl.exceptions import BadRequestError, PterodactylApiError
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from yarl import URL

from homeassistant.components.pterodactyl.sensor import (
    KEY_CPU_LIMIT,
    KEY_CPU_UTILIZATION,
    KEY_DISK_LIMIT,
    KEY_DISK_USAGE,
    KEY_MEMORY_LIMIT,
    KEY_MEMORY_USAGE,
    KEY_NETWORK_INBOUND,
    KEY_NETWORK_OUTBOUND,
    KEY_UPTIME,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .const import SERVER_1_IDENTIFIER, SERVER_2_IDENTIFIER, TEST_URL

UTILIZATION_SENSOR_KEYS = (
    KEY_CPU_UTILIZATION,
    KEY_MEMORY_USAGE,
    KEY_DISK_USAGE,
    KEY_NETWORK_INBOUND,
    KEY_NETWORK_OUTBOUND,
    KEY_UPTIME,
)
NON_UTILIZATION_SENSOR_KEYS = (
    KEY_CPU_LIMIT,
    KEY_MEMORY_LIMIT,
    KEY_DISK_LIMIT,
)
SENSOR_KEYS = (*UTILIZATION_SENSOR_KEYS, *NON_UTILIZATION_SENSOR_KEYS)
DISABLED_SENSOR_KEYS = (
    *NON_UTILIZATION_SENSOR_KEYS,
    KEY_NETWORK_INBOUND,
    KEY_NETWORK_OUTBOUND,
)
ENABLED_SENSOR_KEYS = tuple(
    sensor_key for sensor_key in SENSOR_KEYS if sensor_key not in DISABLED_SENSOR_KEYS
)
GAME_SERVER_IDENTIFIERS = (SERVER_1_IDENTIFIER, SERVER_2_IDENTIFIER)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_pterodactyl")
@pytest.mark.freeze_time("2026-01-01T12:00:00+00:00")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors."""
    with patch("homeassistant.components.pterodactyl._PLATFORMS", [Platform.SENSOR]):
        mock_config_entry = await setup_integration(hass, mock_config_entry)

        sensors = len(hass.states.async_all(Platform.SENSOR))
        assert sensors == len(GAME_SERVER_IDENTIFIERS) * len(SENSOR_KEYS)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.usefixtures("mock_pterodactyl")
async def test_sensor_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test limit and network sensors are disabled by default."""
    await setup_integration(hass, mock_config_entry)

    sensors = len(hass.states.async_all(Platform.SENSOR))
    assert sensors == len(GAME_SERVER_IDENTIFIERS) * len(ENABLED_SENSOR_KEYS)

    for server_identifier in GAME_SERVER_IDENTIFIERS:
        for sensor_key in DISABLED_SENSOR_KEYS:
            entity_id = f"sensor.test_server_{server_identifier}_{sensor_key}"
            assert hass.states.get(entity_id) is None
            entry = entity_registry.async_get(entity_id)
            assert entry is not None
            assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("mock_pterodactyl")
async def test_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test values of all enabled sensors change after an update."""
    await setup_integration(hass, mock_config_entry)

    initial_sensor_states = {}

    for server_identifier in GAME_SERVER_IDENTIFIERS:
        for sensor_key in ENABLED_SENSOR_KEYS:
            entity_id = f"sensor.test_server_{server_identifier}_{sensor_key}"
            state = hass.states.get(entity_id)
            assert state is not None
            initial_sensor_states[entity_id] = state.state

    mock_pterodactyl.client.servers.get_server_utilization.return_value = {
        "current_state": "running",
        "is_suspended": False,
        "resources": {
            "memory_bytes": 2_222_000_000,
            "cpu_absolute": 55,
            "disk_bytes": 4_444_000_000,
            "network_rx_bytes": 44,
            "network_tx_bytes": 55,
            "uptime": 7777,
        },
    }

    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    expected_sensor_values = {
        KEY_CPU_UTILIZATION: "55",
        KEY_MEMORY_USAGE: "2.222",
        KEY_DISK_USAGE: "4.444",
    }
    expected_uptime = (dt_util.utcnow() - timedelta(milliseconds=7777)).isoformat(
        timespec="seconds"
    )

    for server_identifier in GAME_SERVER_IDENTIFIERS:
        for sensor_key in ENABLED_SENSOR_KEYS:
            entity_id = f"sensor.test_server_{server_identifier}_{sensor_key}"
            state = hass.states.get(entity_id)
            assert state is not None

            if sensor_key == KEY_UPTIME:
                assert state.state == expected_uptime
            else:
                assert state.state == expected_sensor_values[sensor_key]


@pytest.mark.usefixtures("mock_pterodactyl")
@pytest.mark.freeze_time("2026-01-01T12:00:00+00:00")
@pytest.mark.parametrize(
    ("deviation_ms", "expected_deviation_ms"),
    [
        pytest.param(-4_999, 0, id="earlier-below-threshold"),
        pytest.param(4_999, 0, id="later-below-threshold"),
        pytest.param(-5_000, -5_000, id="earlier-at-threshold"),
        pytest.param(5_000, 5_000, id="later-at-threshold"),
    ],
)
async def test_uptime_sensor_stability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
    deviation_ms: int,
    expected_deviation_ms: int,
) -> None:
    """Test uptime stability around the 5 second drift tolerance."""
    await setup_integration(hass, mock_config_entry)

    entity_id = f"sensor.test_server_{SERVER_1_IDENTIFIER}_{KEY_UPTIME}"
    initial_state = hass.states.get(entity_id)
    assert initial_state is not None
    initial_last_reported = initial_state.last_reported
    initial_start_time = dt_util.utcnow() - timedelta(milliseconds=6_666)
    assert initial_state.state == initial_start_time.isoformat(timespec="seconds")
    expected_start_time = initial_start_time + timedelta(
        milliseconds=expected_deviation_ms
    )

    utilization = mock_pterodactyl.client.servers.get_server_utilization.return_value
    utilization["resources"]["uptime"] = 6_666 + 60_000 - deviation_ms

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_start_time.isoformat(timespec="seconds")
    assert state.last_reported > initial_last_reported


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "suspended_game_servers", "mock_pterodactyl"
)
async def test_sensor_suspended_server(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
) -> None:
    """Test sensors of suspended servers have no values."""
    await setup_integration(hass, mock_config_entry)

    sensors = hass.states.async_all(Platform.SENSOR)
    assert len(sensors) == len(GAME_SERVER_IDENTIFIERS) * len(SENSOR_KEYS)
    assert {state.entity_id for state in sensors if state.state == STATE_UNKNOWN} == {
        f"sensor.test_server_{server_identifier}_{sensor_key}"
        for server_identifier in GAME_SERVER_IDENTIFIERS
        for sensor_key in UTILIZATION_SENSOR_KEYS
    }
    assert {state.entity_id for state in sensors if state.state != STATE_UNKNOWN} == {
        f"sensor.test_server_{server_identifier}_{sensor_key}"
        for server_identifier in GAME_SERVER_IDENTIFIERS
        for sensor_key in NON_UTILIZATION_SENSOR_KEYS
    }
    mock_pterodactyl.client.servers.get_server_utilization.assert_not_called()


@pytest.mark.parametrize(
    ("api_error", "expected_flow_sources"),
    [
        pytest.param(PterodactylApiError, [], id="pterodactyl_api_error"),
        pytest.param(BadRequestError, [], id="bad_request_error"),
        pytest.param(ClientError, [], id="client_error"),
        pytest.param(TimeoutError, [], id="timeout"),
        pytest.param(
            ClientResponseError(
                request_info=Mock(real_url=URL(TEST_URL)),
                history=[],
                status=500,
            ),
            [],
            id="connection_error",
        ),
        pytest.param(
            ClientResponseError(
                request_info=Mock(real_url=URL(TEST_URL)),
                history=[],
                status=401,
            ),
            [SOURCE_REAUTH],
            id="unauthorized",
        ),
    ],
)
async def test_sensor_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
    api_error: Exception | type[Exception],
    expected_flow_sources: list[str],
) -> None:
    """Test sensors become unavailable after a failed update."""
    await setup_integration(hass, mock_config_entry)

    mock_pterodactyl.client.servers.get_server.side_effect = api_error

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    sensors = hass.states.async_all(Platform.SENSOR)
    assert len(sensors) == len(GAME_SERVER_IDENTIFIERS) * len(ENABLED_SENSOR_KEYS)
    assert all(state.state == STATE_UNAVAILABLE for state in sensors)
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == expected_flow_sources


async def test_sensor_recovery_after_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors recover after a failed update."""
    await setup_integration(hass, mock_config_entry)

    initial_sensor_states = {}

    for server_identifier in GAME_SERVER_IDENTIFIERS:
        for sensor_key in ENABLED_SENSOR_KEYS:
            entity_id = f"sensor.test_server_{server_identifier}_{sensor_key}"
            state = hass.states.get(entity_id)
            assert state is not None
            initial_sensor_states[entity_id] = state.state

    get_server = mock_pterodactyl.client.servers.get_server
    original_side_effect = get_server.side_effect
    get_server.side_effect = ClientConnectionError("Simulated connection error")

    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    sensors = hass.states.async_all(Platform.SENSOR)
    assert len(sensors) == len(GAME_SERVER_IDENTIFIERS) * len(ENABLED_SENSOR_KEYS)
    assert all(state.state == STATE_UNAVAILABLE for state in sensors)

    get_server.side_effect = original_side_effect
    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    sensors = hass.states.async_all(Platform.SENSOR)
    assert len(sensors) == len(GAME_SERVER_IDENTIFIERS) * len(ENABLED_SENSOR_KEYS)
    recovered_sensor_states = {state.entity_id: state.state for state in sensors}
    assert recovered_sensor_states.keys() == initial_sensor_states.keys()
    expected_uptime = (dt_util.utcnow() - timedelta(milliseconds=6666)).isoformat(
        timespec="seconds"
    )

    for entity_id, initial_state in initial_sensor_states.items():
        recovered_state = recovered_sensor_states[entity_id]

        if entity_id.endswith(f"_{KEY_UPTIME}"):
            assert recovered_state == expected_uptime
        else:
            assert recovered_state == initial_state
