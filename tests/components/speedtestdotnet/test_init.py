"""Tests for SpeedTest integration."""

from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch, sentinel

import speedtest

from homeassistant.components.speedtestdotnet.const import (
    CONF_SERVER_ID,
    CONF_SERVER_NAME,
    DOMAIN,
)
from homeassistant.components.speedtestdotnet.coordinator import (
    SpeedTestDataCoordinator,
    _get_dynamic_servers,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import MOCK_RESULTS, MOCK_SERVERS

from tests.common import MockConfigEntry, async_fire_time_changed

DYNAMIC_SERVER = {
    "url": "http://server_3:8080/speedtest/upload.php",
    "lat": "3",
    "lon": "3",
    "name": "Server3",
    "country": "Country3",
    "cc": "LL3",
    "sponsor": "Sponsor3",
    "id": "3",
    "host": "server3:8080",
    "d": 0.5,
}
DYNAMIC_SERVERS = {0.5: [DYNAMIC_SERVER]}


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


def test_get_dynamic_servers() -> None:
    """Test retrieving servers from the dynamic endpoint."""
    api = MagicMock()
    api.config = {"threads": {"download": 8}, "ignore_servers": [2]}
    api.lat_lon = (60.0, 24.0)
    setattr(api, "_opener", sentinel.opener)
    setattr(api, "_secure", True)
    response = MagicMock()
    response.code = 200
    servers_xml = (
        b"<settings><servers>"
        b'<server url="http://server_1:8080/speedtest/upload.php" '
        b'lat="60.1" lon="24.1" name="Helsinki" '
        b'country="Finland" cc="FI" sponsor="Sponsor1" '
        b'id="1" host="server1:8080" />'
        b'<server url="http://server_2:8080/speedtest/upload.php" '
        b'lat="60.2" lon="24.2" name="Ignored" '
        b'country="Finland" cc="FI" sponsor="Sponsor2" '
        b'id="2" host="server2:8080" />'
        b'<server url="http://server_3:8080/speedtest/upload.php" '
        b'lat="broken" lon="24.3" name="Invalid" '
        b'country="Finland" cc="FI" sponsor="Sponsor3" '
        b'id="3" host="server3:8080" />'
        b"</servers></settings>"
    )

    with (
        patch(
            "homeassistant.components.speedtestdotnet.coordinator.speedtest.gzip",
            object(),
        ),
        patch(
            "homeassistant.components.speedtestdotnet.coordinator.speedtest.build_request",
            return_value=sentinel.request,
        ) as mock_build_request,
        patch(
            "homeassistant.components.speedtestdotnet.coordinator.speedtest.catch_request",
            return_value=(response, False),
        ) as mock_catch_request,
        patch(
            "homeassistant.components.speedtestdotnet.coordinator.speedtest.get_response_stream",
            return_value=BytesIO(servers_xml),
        ),
    ):
        servers = _get_dynamic_servers(api, servers=["1"])

    mock_build_request.assert_called_once_with(
        "://www.speedtest.net/speedtest-servers.php?threads=8",
        headers={"Accept-Encoding": "gzip"},
        secure=True,
    )
    mock_catch_request.assert_called_once_with(
        sentinel.request, opener=sentinel.opener
    )
    response.close.assert_called_once()
    server = next(iter(servers.values()))[0]
    assert server["id"] == "1"
    assert server["name"] == "Helsinki"
    assert isinstance(server["d"], float)


def test_update_servers_adds_dynamic_servers(hass: HomeAssistant) -> None:
    """Test dynamic servers are added to the available server list."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    api = MagicMock()
    api.get_servers.return_value = {1: [MOCK_SERVERS[1][0]]}

    with patch(
        "homeassistant.components.speedtestdotnet.coordinator._get_dynamic_servers",
        return_value=DYNAMIC_SERVERS,
    ) as mock_get_dynamic_servers:
        coordinator = SpeedTestDataCoordinator(hass, entry, api)
        coordinator.update_servers()

    mock_get_dynamic_servers.assert_called_once_with(api)
    assert "Country1 - Sponsor1 - Server1" in coordinator.servers
    assert "Country3 - Sponsor3 - Server3" in coordinator.servers


def test_update_data_falls_back_to_dynamic_selected_server(
    hass: HomeAssistant,
) -> None:
    """Test selected servers can be retrieved from the dynamic endpoint."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_SERVER_ID: "3"},
    )
    entry.add_to_hass(hass)
    api = MagicMock()
    api.closest = []
    api.get_servers.return_value = {1: [MOCK_SERVERS[1][0]]}
    api.get_best_server.return_value = DYNAMIC_SERVER
    api.results.dict.return_value = MOCK_RESULTS

    with patch(
        "homeassistant.components.speedtestdotnet.coordinator._get_dynamic_servers",
        side_effect=[speedtest.ServersRetrievalError(), DYNAMIC_SERVERS],
    ) as mock_get_dynamic_servers:
        coordinator = SpeedTestDataCoordinator(hass, entry, api)
        assert coordinator.update_data() == MOCK_RESULTS

    assert api.servers == DYNAMIC_SERVERS
    mock_get_dynamic_servers.assert_called_with(api, servers=["3"])
    api.get_best_server.assert_called_once()
