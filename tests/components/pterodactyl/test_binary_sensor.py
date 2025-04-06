"""Tests for Minecraft Server binary sensor."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from requests.exceptions import ConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("setup_mock_config_entry")
async def test_binary_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor."""
    assert len(hass.states.async_all(Platform.BINARY_SENSOR)) == 2
    assert hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_1_status") == snapshot
    assert hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_2_status") == snapshot


@pytest.mark.usefixtures("setup_mock_config_entry")
async def test_binary_sensor_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor update."""
    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(Platform.BINARY_SENSOR)) == 2
    assert hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_1_status") == snapshot
    assert hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_2_status") == snapshot


@pytest.mark.usefixtures("setup_mock_config_entry")
async def test_binary_sensor_update_failure(
    hass: HomeAssistant,
    mock_pterodactyl: Generator[AsyncMock],
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test failed binary sensor update."""
    mock_pterodactyl.client.servers.get_server.side_effect = ConnectionError(
        "Simulated connection error"
    )

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(hass.states.async_all(Platform.BINARY_SENSOR)) == 2
    assert hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_1_status") == snapshot
    assert hass.states.get(f"{Platform.BINARY_SENSOR}.test_server_2_status") == snapshot
