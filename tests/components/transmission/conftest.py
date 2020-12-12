"""Fixtures for the Transmission integration tests."""
import json
from unittest.mock import patch

import pytest
from transmissionrpc.error import TransmissionError

from homeassistant.components.transmission import (
    CONF_HOST,
    CONF_LIMIT,
    CONF_NAME,
    CONF_ORDER,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.components.transmission.const import (
    ORDER_BEST_RATIO_FIRST,
    ORDER_NEWEST_FIRST,
    ORDER_OLDEST_FIRST,
    ORDER_WORST_RATIO_FIRST,
)

from tests.common import MockConfigEntry, load_fixture

MOCK_TORRENTS_OLDEST_TO_NEWEST = [2, 1, 3, 4, 5]
MOCK_TORRENTS_BEST_TO_WORST = [3, 1, 5, 2, 4]


@pytest.fixture(name="api")
def mock_transmission_api():
    """Mock an api."""
    with patch("transmissionrpc.Client"):
        yield


@pytest.fixture(name="auth_error")
def mock_api_authentication_error():
    """Mock an api."""
    with patch(
        "transmissionrpc.Client", side_effect=TransmissionError("401: Unauthorized")
    ):
        yield


@pytest.fixture(name="conn_error")
def mock_api_connection_error():
    """Mock an api."""
    with patch(
        "transmissionrpc.Client",
        side_effect=TransmissionError("111: Connection refused"),
    ):
        yield


@pytest.fixture(name="unknown_error")
def mock_api_unknown_error():
    """Mock an api."""
    with patch("transmissionrpc.Client", side_effect=TransmissionError):
        yield


@pytest.fixture(name="transmission_setup")
def transmission_setup_fixture():
    """Mock transmission entry setup."""
    with patch(
        "homeassistant.components.transmission.async_setup_entry", return_value=True
    ):
        yield


def get_correct_fixture(*args):
    """Return the appropriate JSON string."""
    method = json.loads(args[0])["method"]
    if method == "torrent-get":
        return load_fixture("transmission-torrents-get.json")
    if method == "session-get":
        return load_fixture("transmission-session-get.json")
    if method == "session-stats":
        return load_fixture("transmission-session-stats.json")
    return ""


def setup_transmission(
    hass,
    name="Transmission",
    host="0.0.0.0",
    username="user",
    password="pass",
    port=9091,
    limit=20,
    order=ORDER_OLDEST_FIRST,
):
    """Init the mock Transmission entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: name,
            CONF_HOST: host,
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_PORT: port,
            CONF_LIMIT: limit,
            CONF_ORDER: order,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="torrent_info")
async def mock_torrent_info(hass):
    """Mock Transmission setup with response from the RPC."""
    entry = setup_transmission(hass)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="status_seeding")
async def mock_torrent_seeding(hass):
    """Mock Transmission setup with response from the RPC, seeding."""
    # pylint: disable=protected-access
    entry = setup_transmission(hass)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        tm_client = hass.data[DOMAIN][entry.entry_id]
        tm_client._tm_data.data.downloadSpeed = 0
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="status_downloading")
async def mock_torrent_downloading(hass):
    """Mock Transmission setup with response from the RPC, downloading."""
    # pylint: disable=protected-access
    entry = setup_transmission(hass)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        tm_client = hass.data[DOMAIN][entry.entry_id]
        tm_client._tm_data.data.uploadSpeed = 0
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="status_idle")
async def mock_torrent_idle(hass):
    """Mock Transmission setup with response from the RPC, idle."""
    # pylint: disable=protected-access
    entry = setup_transmission(hass)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        tm_client = hass.data[DOMAIN][entry.entry_id]
        tm_client._tm_data.data.uploadSpeed = 0
        tm_client._tm_data.data.downloadSpeed = 0
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="torrent_limit")
async def mock_torrent_limit(hass):
    """Mock Transmission setup with response from the RPC."""
    entry = setup_transmission(hass, limit=2)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="torrent_order_recent")
async def mock_torrent_order_recent(hass):
    """Mock Transmission setup with response from the RPC."""
    entry = setup_transmission(hass, order=ORDER_NEWEST_FIRST)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="torrent_order_recent_limit")
async def mock_torrent_order_recent_limit(hass):
    """Mock Transmission setup with response from the RPC."""
    entry = setup_transmission(hass, limit=2, order=ORDER_NEWEST_FIRST)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="torrent_order_ratio")
async def mock_torrent_order_ratio(hass):
    """Mock Transmission setup with response from the RPC."""
    entry = setup_transmission(hass, order=ORDER_BEST_RATIO_FIRST)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="torrent_order_ratio_limit")
async def mock_torrent_order_ratio_limit(hass):
    """Mock Transmission setup with response from the RPC."""
    entry = setup_transmission(hass, limit=2, order=ORDER_BEST_RATIO_FIRST)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="torrent_order_ratio_worst")
async def mock_torrent_order_ratio_worst(hass):
    """Mock Transmission setup with response from the RPC."""
    entry = setup_transmission(hass, order=ORDER_WORST_RATIO_FIRST)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="torrent_order_ratio_worst_limit")
async def mock_torrent_order_ratio_worst_limit(hass):
    """Mock Transmission setup with response from the RPC."""
    entry = setup_transmission(hass, limit=2, order=ORDER_WORST_RATIO_FIRST)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield
