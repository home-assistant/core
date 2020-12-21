"""Fixtures for the Transmission integration tests."""
import json

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
from homeassistant.components.transmission.const import ORDER_OLDEST_FIRST

from tests.async_mock import patch
from tests.common import MockConfigEntry, load_fixture

MOCK_TORRENTS_OLDEST_TO_NEWEST = [2, 1, 3, 4, 5]
MOCK_TORRENTS_BEST_TO_WORST = [3, 1, 5, 2, 4]
MOCK_LIMIT_INITIAL = 20
MOCK_LIMIT_TRUNCATED = 2


def setup_transmission(
    hass,
    name="Transmission",
    host="0.0.0.0",
    username="user",
    password="pass",
    port=9091,
    limit=MOCK_LIMIT_INITIAL,
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


async def mock_client_setup(hass, entry=None):
    """Mock Transmission client setup."""
    if entry is None:
        entry = setup_transmission(hass)
    with patch("transmissionrpc.Client._http_query", side_effect=get_correct_fixture):
        await hass.config_entries.async_setup(entry.entry_id)
        return hass.data[DOMAIN][entry.entry_id]


@pytest.fixture(name="torrent_info")
async def mock_torrent_info(hass):
    """Mock Transmission setup with response from the RPC."""
    entry = setup_transmission(hass)
    with patch(
        "homeassistant.components.transmission.transmissionrpc.Client._http_query",
        side_effect=get_correct_fixture,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="api")
def mock_transmission_api():
    """Mock an api."""
    with patch("homeassistant.components.transmission.transmissionrpc.Client"):
        yield


@pytest.fixture(name="auth_error")
def mock_api_authentication_error():
    """Mock an api."""
    with patch(
        "homeassistant.components.transmission.transmissionrpc.Client",
        side_effect=TransmissionError("401: Unauthorized"),
    ):
        yield


@pytest.fixture(name="conn_error")
def mock_api_connection_error():
    """Mock an api."""
    with patch(
        "homeassistant.components.transmission.transmissionrpc.Client",
        side_effect=TransmissionError("111: Connection refused"),
    ):
        yield


@pytest.fixture(name="unknown_error")
def mock_api_unknown_error():
    """Mock an api."""
    with patch(
        "homeassistant.components.transmission.transmissionrpc.Client",
        side_effect=TransmissionError,
    ):
        yield


@pytest.fixture(name="transmission_setup")
def transmission_setup_fixture():
    """Mock transmission entry setup."""
    with patch(
        "homeassistant.components.transmission.async_setup_entry", return_value=True
    ):
        yield
