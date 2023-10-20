"""Tests for Minecraft Server binary sensor."""
from datetime import timedelta
from unittest.mock import patch

from mcstatus import BedrockServer, JavaServer
from mcstatus.status_response import BedrockStatusResponse, JavaStatusResponse
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
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
async def test_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: JavaServer | BedrockServer,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor."""
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
        assert hass.states.get("binary_sensor.minecraft_server_status") == snapshot


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "status_response"),
    [
        ("java_mock_config_entry", JavaServer, TEST_JAVA_STATUS_RESPONSE),
        ("bedrock_mock_config_entry", BedrockServer, TEST_BEDROCK_STATUS_RESPONSE),
    ],
)
async def test_binary_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: JavaServer | BedrockServer,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor update."""
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
        assert hass.states.get("binary_sensor.minecraft_server_status") == snapshot


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "status_response"),
    [
        ("java_mock_config_entry", JavaServer, TEST_JAVA_STATUS_RESPONSE),
        ("bedrock_mock_config_entry", BedrockServer, TEST_BEDROCK_STATUS_RESPONSE),
    ],
)
async def test_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: JavaServer | BedrockServer,
    status_response: JavaStatusResponse | BedrockStatusResponse,
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
        assert hass.states.get("binary_sensor.minecraft_server_status") == snapshot
