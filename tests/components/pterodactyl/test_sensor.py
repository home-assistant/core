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

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_URL

CPU_ENTITY_ID = "sensor.test_server_1_cpu_utilization"
UPTIME_ENTITY_ID = "sensor.test_server_1_uptime"


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

        assert len(hass.states.async_all(Platform.SENSOR)) == 18
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

    assert len(hass.states.async_all(Platform.SENSOR)) == 8
    for key in (
        "cpu_limit",
        "memory_limit",
        "disk_limit",
        "network_inbound",
        "network_outbound",
    ):
        entity_id = f"sensor.test_server_1_{key}"
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
    """Test sensor values change after an update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CPU_ENTITY_ID).state == "22"

    mock_pterodactyl.client.servers.get_server_utilization.return_value = {
        "current_state": "running",
        "is_suspended": False,
        "resources": {
            "memory_bytes": 1111,
            "cpu_absolute": 55,
            "disk_bytes": 3333,
            "network_rx_bytes": 44,
            "network_tx_bytes": 55,
            "uptime": 6666,
        },
    }

    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(CPU_ENTITY_ID).state == "55"


@pytest.mark.usefixtures("suspended_game_servers", "mock_pterodactyl")
async def test_sensor_suspended_server(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
) -> None:
    """Test sensors of a suspended server have no values."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CPU_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(UPTIME_ENTITY_ID).state == STATE_UNKNOWN
    mock_pterodactyl.client.servers.get_server_utilization.assert_not_called()


@pytest.mark.parametrize(
    "api_error",
    [
        pytest.param(PterodactylApiError, id="pterodactyl_api_error"),
        pytest.param(BadRequestError, id="bad_request_error"),
        pytest.param(ClientError, id="client_error"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(
            ClientResponseError(
                request_info=Mock(real_url=URL(TEST_URL)),
                history=[],
                status=500,
            ),
            id="connection_error",
        ),
    ],
)
async def test_sensor_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
    api_error: Exception | type[Exception],
) -> None:
    """Test sensors become unavailable on failed updates."""
    await setup_integration(hass, mock_config_entry)

    mock_pterodactyl.client.servers.get_server.side_effect = api_error

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    sensors = hass.states.async_all(Platform.SENSOR)
    assert len(sensors) == 8
    assert all(state.state == STATE_UNAVAILABLE for state in sensors)
    assert hass.config_entries.flow.async_progress() == []


async def test_sensor_update_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an authorization error during updates starts reauthentication."""
    await setup_integration(hass, mock_config_entry)

    mock_pterodactyl.client.servers.get_server.side_effect = ClientResponseError(
        request_info=Mock(real_url=URL(TEST_URL)),
        history=[],
        status=401,
    )

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(CPU_ENTITY_ID).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_sensor_recovery_after_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors recover after a failed update."""
    await setup_integration(hass, mock_config_entry)

    get_server = mock_pterodactyl.client.servers.get_server
    original_side_effect = get_server.side_effect
    get_server.side_effect = ClientConnectionError("Simulated connection error")

    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(CPU_ENTITY_ID).state == STATE_UNAVAILABLE

    get_server.side_effect = original_side_effect
    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(CPU_ENTITY_ID).state == "22"
