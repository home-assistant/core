"""The tests for Kodi binary sensor platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.kodi.const import (
    CONF_WS_PORT,
    DOMAIN,
    WS_DPMS,
    WS_SCREENSAVER,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .util import MockConnection, MockWSConnection

from tests.common import MockConfigEntry

PATCH_KODI = "homeassistant.components.kodi"
PATCH_KODI_CONNMAN = f"{PATCH_KODI}.connection_manager.KodiConnectionManager"

TEST_KODI_CONFIG = {
    CONF_NAME: "name",
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 8080,
    CONF_WS_PORT: 9090,
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_SSL: False,
}


def pytest_configure(config):
    """Define custom markers."""
    config.addinivalue_line(
        "markers", "connected: Mark if kodi connection will be connected."
    )
    config.addinivalue_line(
        "markers", "use_websocket: If kodi connection uses websocket or HTML."
    )


@pytest.fixture
def mock_ws_callbacks():
    """Use to catch websocket api_method callbacks."""
    with patch(  # Catching all websocket callbacks
        f"{PATCH_KODI_CONNMAN}.register_websocket_callback", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def mock_kodi_version():
    """Return a valid Kodi version."""
    with patch(  # To start connman without errors
        "pykodi.Kodi.get_application_properties",
        return_value={"version": {"major": 1, "minor": 1}},
    ) as mock:
        yield mock


@pytest.fixture
def mock_sensors_init():
    """Initialize binary sensors as on."""
    with patch(  # Init binary sensors true
        "pykodi.Kodi.call_method",
        return_value={WS_SCREENSAVER["boolean"]: True, WS_DPMS["boolean"]: True},
    ) as mock:
        yield mock


@pytest.fixture
async def kodi_connection(hass: HomeAssistant, request):
    """Initialize a mocked connection to kodi.

    Customize the connection with markers: connected, use_websocket
    """
    marker = request.node.get_closest_marker("connected")
    if marker is None:
        connected = False
    else:
        connected = True

    marker = request.node.get_closest_marker("use_websocket")
    if marker is None:
        use_ws = False
    else:
        use_ws = True

    entry_data = {**TEST_KODI_CONFIG}
    if not use_ws:
        entry_data[CONF_WS_PORT] = None
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, title="name")
    entry.add_to_hass(hass)

    conn = MockWSConnection if use_ws else MockConnection
    with patch(
        f"{PATCH_KODI}.connection_manager.get_kodi_connection",
        return_value=conn(connected),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
