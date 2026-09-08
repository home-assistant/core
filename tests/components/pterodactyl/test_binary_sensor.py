"""Tests for the binary sensor platform of the Pterodactyl integration."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pydactyl.responses import PaginatedResponse
import pytest
from requests.exceptions import ConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)


@pytest.mark.usefixtures("mock_pterodactyl")
async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor."""
    with patch(
        "homeassistant.components.pterodactyl._PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        mock_config_entry = await setup_integration(hass, mock_config_entry)

        assert len(hass.states.async_all(Platform.BINARY_SENSOR)) == 4
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.usefixtures("mock_pterodactyl")
async def test_binary_sensor_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor update."""
    await setup_integration(hass, mock_config_entry)

    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(Platform.BINARY_SENSOR)) == 4
    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_1_status").state
        == STATE_ON
    )
    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_2_status").state
        == STATE_ON
    )
    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_1_suspended").state
        == "off"
    )
    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_2_suspended").state
        == "off"
    )


@pytest.mark.usefixtures("mock_pterodactyl")
async def test_binary_sensor_suspended_server(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
) -> None:
    """Test a suspended server does not fetch utilization data."""
    server_list_data = await async_load_json_object_fixture(
        hass, "suspended_server_list_data.json", "pterodactyl"
    )
    server_1_data = await async_load_json_object_fixture(
        hass, "suspended_server_data.json", "pterodactyl"
    )

    mock_pterodactyl.client.servers.list_servers.return_value = PaginatedResponse(
        mock_pterodactyl,
        "client",
        server_list_data,
    )
    server_data = {"1": server_1_data}
    mock_pterodactyl.client.servers.get_server.side_effect = lambda identifier: (
        server_data[identifier]
    )

    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_1_status").state == "off"
    )
    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_1_suspended").state
        == STATE_ON
    )
    mock_pterodactyl.client.servers.get_server_utilization.assert_not_called()


async def test_binary_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pterodactyl: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test failed binary sensor update."""
    await setup_integration(hass, mock_config_entry)

    mock_pterodactyl.client.servers.get_server.side_effect = ConnectionError(
        "Simulated connection error"
    )

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(hass.states.async_all(Platform.BINARY_SENSOR)) == 4
    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_1_status").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_2_status").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_1_suspended").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_2_suspended").state
        == STATE_UNAVAILABLE
    )
