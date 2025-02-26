"""Tests for Minecraft Server binary sensor."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from mcstatus import BedrockServer, JavaServer
from mcstatus.status_response import BedrockStatusResponse, JavaStatusResponse
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant

from .const import (
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_PORT,
)

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "lookup_function_name", "status_response"),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
        ),
    ],
)
async def test_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor."""
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
        assert (
            hass.states.get("binary_sensor.mc_dummyserver_com_25566_status") == snapshot
        )


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "lookup_function_name", "status_response"),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
        ),
    ],
)
async def test_binary_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor update."""
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
        assert (
            hass.states.get("binary_sensor.mc_dummyserver_com_25566_status") == snapshot
        )


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "lookup_function_name", "status_response"),
    [
        (
            "java_mock_config_entry",
            JavaServer,
            "async_lookup",
            TEST_JAVA_STATUS_RESPONSE,
        ),
        (
            "bedrock_mock_config_entry",
            BedrockServer,
            "lookup",
            TEST_BEDROCK_STATUS_RESPONSE,
        ),
    ],
)
async def test_binary_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry: str,
    server: JavaServer | BedrockServer,
    lookup_function_name: str,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    request: pytest.FixtureRequest,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test failed binary sensor update."""
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
        assert (
            hass.states.get("binary_sensor.mc_dummyserver_com_25566_status").state
            == STATE_OFF
        )
