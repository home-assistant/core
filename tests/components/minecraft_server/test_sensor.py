"""Tests for Minecraft Server sensors."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from mcstatus import BedrockServer, JavaServer
from mcstatus.responses import BedrockStatusResponse, JavaStatusResponse
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .const import (
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_PORT,
)

from tests.common import async_fire_time_changed

JAVA_SENSOR_ENTITIES: list[str] = [
    "sensor.mc_dummyserver_com_25566_latency",
    "sensor.mc_dummyserver_com_25566_players_online",
    "sensor.mc_dummyserver_com_25566_players_max",
    "sensor.mc_dummyserver_com_25566_world_message",
    "sensor.mc_dummyserver_com_25566_version",
    "sensor.mc_dummyserver_com_25566_protocol_version",
]

JAVA_SENSOR_ENTITIES_DISABLED_BY_DEFAULT: list[str] = [
    "sensor.mc_dummyserver_com_25566_players_max",
    "sensor.mc_dummyserver_com_25566_protocol_version",
]

BEDROCK_SENSOR_ENTITIES: list[str] = [
    "sensor.mc_dummyserver_com_25566_latency",
    "sensor.mc_dummyserver_com_25566_players_online",
    "sensor.mc_dummyserver_com_25566_players_max",
    "sensor.mc_dummyserver_com_25566_world_message",
    "sensor.mc_dummyserver_com_25566_version",
    "sensor.mc_dummyserver_com_25566_protocol_version",
    "sensor.mc_dummyserver_com_25566_map_name",
    "sensor.mc_dummyserver_com_25566_game_mode",
    "sensor.mc_dummyserver_com_25566_edition",
]

BEDROCK_SENSOR_ENTITIES_DISABLED_BY_DEFAULT: list[str] = [
    "sensor.mc_dummyserver_com_25566_players_max",
    "sensor.mc_dummyserver_com_25566_protocol_version",
    "sensor.mc_dummyserver_com_25566_edition",
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    (
        "mock_config_entry",
        "server",
        "lookup_function_name",
        "status_response",
        "entity_ids",
    ),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
            BEDROCK_SENSOR_ENTITIES,
        ),
    ],
)
async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    entity_ids: list[str],
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.{lookup_function_name}",
            return_value=server(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
            return_value=status_response,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        for entity_id in entity_ids:
            assert hass.states.get(entity_id) == snapshot


@pytest.mark.parametrize(
    (
        "mock_config_entry",
        "server",
        "lookup_function_name",
        "status_response",
        "entity_ids",
    ),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES_DISABLED_BY_DEFAULT,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
            BEDROCK_SENSOR_ENTITIES_DISABLED_BY_DEFAULT,
        ),
    ],
)
async def test_sensor_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    entity_ids: list[str],
    request: pytest.FixtureRequest,
) -> None:
    """Test sensor, which is disabled by default."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.{lookup_function_name}",
            return_value=server(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
            return_value=status_response,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        for entity_id in entity_ids:
            assert not hass.states.get(entity_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    (
        "mock_config_entry",
        "server",
        "lookup_function_name",
        "status_response",
        "entity_ids",
    ),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
            BEDROCK_SENSOR_ENTITIES,
        ),
    ],
)
async def test_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    entity_ids: list[str],
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor update."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.{lookup_function_name}",
            return_value=server(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
            return_value=status_response,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        for entity_id in entity_ids:
            assert hass.states.get(entity_id) == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    (
        "mock_config_entry",
        "server",
        "lookup_function_name",
        "status_response",
        "entity_ids",
    ),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
            JAVA_SENSOR_ENTITIES,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
            BEDROCK_SENSOR_ENTITIES,
        ),
    ],
)
async def test_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    entity_ids: list[str],
    request: pytest.FixtureRequest,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test failed sensor update."""
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.{lookup_function_name}",
            return_value=server(host=TEST_HOST, port=TEST_PORT),
        ),
        patch(
            f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
            return_value=status_response,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        f"homeassistant.components.minecraft_server.api.{server.__name__}.async_status",
        side_effect=OSError,
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        for entity_id in entity_ids:
            assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
