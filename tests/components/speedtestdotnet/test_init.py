"""Tests for SpeedTest integration."""

from copy import deepcopy
from datetime import timedelta
from http.client import InvalidURL
from unittest.mock import MagicMock

import speedtest

from homeassistant.components.speedtestdotnet.const import (
    CONF_SERVER_ID,
    CONF_SERVER_NAME,
    DOMAIN,
)
from homeassistant.components.speedtestdotnet.coordinator import (
    SpeedTestDataCoordinator,
    _normalize_server_url,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import MOCK_SERVERS

from tests.common import MockConfigEntry, async_fire_time_changed


def test_normalize_server_url() -> None:
    """Test stripping whitespace from a server URL host."""
    server = deepcopy(MOCK_SERVERS[1][0])
    server["url"] = "http:// server_1:8080/speedtest/upload.php"

    _normalize_server_url(server)

    assert server["url"] == "http://server_1:8080/speedtest/upload.php"


async def test_setup_failed(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test SpeedTestDotNet failed due to an error."""

    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = speedtest.ConfigRetrievalError
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_entry_lifecycle(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test the SpeedTestDotNet entry lifecycle."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_SERVER_NAME: "Country1 - Sponsor1 - Server1",
            CONF_SERVER_ID: "1",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, SpeedTestDataCoordinator)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_server_not_found(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test configured server id is not found."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        options={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, SpeedTestDataCoordinator)

    mock_api.return_value.get_servers.side_effect = speedtest.NoMatchedServers
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(minutes=61),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("sensor.speedtest_ping")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_get_best_server_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test configured server id is not found."""

    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, SpeedTestDataCoordinator)

    mock_api.return_value.get_best_server.side_effect = (
        speedtest.SpeedtestBestServerFailure(
            "Unable to connect to servers to test latency."
        )
    )
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.speedtest_ping")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_invalid_server_url(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test malformed server URLs do not raise unexpected errors."""

    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, SpeedTestDataCoordinator)

    mock_api.return_value.get_best_server.side_effect = InvalidURL(
        "URL can't contain control characters"
    )
    await entry.runtime_data.async_refresh()
    assert not entry.runtime_data.last_update_success
