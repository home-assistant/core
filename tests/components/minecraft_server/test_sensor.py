"""Tests for Minecraft Server sensors."""
from datetime import timedelta
from unittest.mock import patch

from mcstatus import BedrockServer, JavaServer
from mcstatus.status_response import BedrockStatusResponse, JavaStatusResponse
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_PORT,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "status_response"),
    [
        ("java_mock_config_entry", JavaServer, TEST_JAVA_STATUS_RESPONSE),
        ("bedrock_mock_config_entry", BedrockServer, TEST_BEDROCK_STATUS_RESPONSE),
    ],
)
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.minecraft_server_latency",
        "sensor.minecraft_server_players_online",
        "sensor.minecraft_server_players_max",
        "sensor.minecraft_server_motd",
        "sensor.minecraft_server_version",
        "sensor.minecraft_server_protocol_version",
        "sensor.minecraft_server_edition",
        "sensor.minecraft_server_map_name",
        "sensor.minecraft_server_game_mode",
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: JavaServer | BedrockServer,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    entity_id: er.EntityRegistry,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with patch(
        f"mcstatus.server.{server.__name__}.lookup",
        return_value=server(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        f"mcstatus.server.{server.__name__}.async_status",
        return_value=status_response,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state == snapshot


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "status_response"),
    [
        ("java_mock_config_entry", JavaServer, TEST_JAVA_STATUS_RESPONSE),
        ("bedrock_mock_config_entry", BedrockServer, TEST_BEDROCK_STATUS_RESPONSE),
    ],
)
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.minecraft_server_latency",
        "sensor.minecraft_server_players_online",
        "sensor.minecraft_server_players_max",
        "sensor.minecraft_server_motd",
        "sensor.minecraft_server_version",
        "sensor.minecraft_server_protocol_version",
        "sensor.minecraft_server_edition",
        "sensor.minecraft_server_map_name",
        "sensor.minecraft_server_game_mode",
    ],
)
async def test_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: JavaServer | BedrockServer,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    entity_id: er.EntityRegistry,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor update."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with patch(
        f"mcstatus.server.{server.__name__}.lookup",
        return_value=server(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        f"mcstatus.server.{server.__name__}.async_status",
        return_value=status_response,  # TODO: Use second test status_response?
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        future = dt_util.utcnow() + timedelta(minutes=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state == snapshot


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "status_response"),
    [
        ("java_mock_config_entry", JavaServer, TEST_JAVA_STATUS_RESPONSE),
        ("bedrock_mock_config_entry", BedrockServer, TEST_BEDROCK_STATUS_RESPONSE),
    ],
)
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.minecraft_server_latency",
        "sensor.minecraft_server_players_online",
        "sensor.minecraft_server_players_max",
        "sensor.minecraft_server_motd",
        "sensor.minecraft_server_version",
        "sensor.minecraft_server_protocol_version",
        "sensor.minecraft_server_edition",
        "sensor.minecraft_server_map_name",
        "sensor.minecraft_server_game_mode",
    ],
)
async def test_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: JavaServer | BedrockServer,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    entity_id: er.EntityRegistry,
    request: pytest.FixtureRequest,
) -> None:
    """Test sensor update."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with patch(
        f"mcstatus.server.{server.__name__}.lookup",
        return_value=server(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        f"mcstatus.server.{server.__name__}.async_status",
        return_value=status_response,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        f"mcstatus.server.{server.__name__}.async_status",
        side_effect=OSError,
    ):
        future = dt_util.utcnow() + timedelta(minutes=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is None
