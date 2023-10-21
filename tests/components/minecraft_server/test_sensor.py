"""Tests for Minecraft Server sensors."""
from datetime import timedelta
from unittest.mock import patch

from mcstatus import BedrockServer, JavaServer
from mcstatus.status_response import BedrockStatusResponse, JavaStatusResponse
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
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
    ("mock_config_entry", "server", "status_response", "entity_id"),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_latency",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_players_online",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_world_message",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_version",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_latency",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_players_online",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_world_message",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_version",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_map_name",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_game_mode",
        ),
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
        f"homeassistant.components.minecraft_server.api.{server.__name__}.lookup",
        return_value=server(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
        return_value=status_response,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id) == snapshot


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "status_response", "entity_id"),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_protocol_version",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_players_max",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_protocol_version",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_players_max",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_edition",
        ),
    ],
)
async def test_sensor_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: JavaServer | BedrockServer,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    entity_id: er.EntityRegistry,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor, which is disabled by default."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.lookup",
        return_value=server(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
        return_value=status_response,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert not hass.states.get(entity_id)


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "status_response", "entity_id"),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_latency",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_players_online",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_world_message",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_version",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_latency",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_players_online",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_world_message",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_version",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_map_name",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_game_mode",
        ),
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
    future = dt_util.utcnow() + timedelta(minutes=1)

    with patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.lookup",
        return_value=server(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
        return_value=status_response,  # TODO: Use second test status_response?
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id) == snapshot


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "status_response", "entity_id"),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_latency",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_players_online",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_world_message",
        ),
        (
            "java_mock_config_entry",
            JavaServer,
            TEST_JAVA_STATUS_RESPONSE,
            "sensor.minecraft_server_version",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_latency",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_players_online",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_world_message",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_version",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_map_name",
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            TEST_BEDROCK_STATUS_RESPONSE,
            "sensor.minecraft_server_game_mode",
        ),
    ],
)
async def test_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: JavaServer | BedrockServer,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    entity_id: er.EntityRegistry,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test failed sensor update."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.lookup",
        return_value=server(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
        return_value=status_response,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    future = dt_util.utcnow() + timedelta(minutes=2)
    with patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
        side_effect=OSError,
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
