"""Tests for the Kodi integration."""
from unittest.mock import patch

from homeassistant.components.kodi.const import CONF_WS_PORT, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)

from .util import MockConnection, MockWSConnection

from tests.common import MockConfigEntry

PATCH_KODI = "homeassistant.components.kodi"
PATCH_KODI_BINARY = f"{PATCH_KODI}.binary_sensor.KodiBinaryEntity"
PATCH_KODI_CONNMAN = f"{PATCH_KODI}.kodi_connman.KodiConnectionManager"
PATCH_KODI_MEDIA = f"{PATCH_KODI}.media_player"


async def init_integration(
    hass, _with_ws: bool = False, _connected: bool = False
) -> MockConfigEntry:
    """Set up the Kodi integration in Home Assistant.

    _with_ws: Setup with websocket connection.
    _connected: If mocked connection signals connected.
    """
    entry_data = {
        CONF_NAME: "name",
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 8080,
        CONF_WS_PORT: 9090,
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
        CONF_SSL: False,
    }
    if not _with_ws:
        entry_data[CONF_WS_PORT] = None
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, title="name")
    entry.add_to_hass(hass)
    conn = MockWSConnection if _with_ws else MockConnection

    with patch(
        f"{PATCH_KODI}.kodi_connman.get_kodi_connection", return_value=conn(_connected)
    ), patch("pykodi.kodi.KodiHTTPConnection.connect", return_value=_connected), patch(
        "pykodi.kodi.KodiWSConnection.connect", return_value=_connected
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def stop_integration(hass):
    """Teardown without error by unregistering the callbacks.

    This is only needed when initializing the integration with websockets.
    """
    with patch(
        f"{PATCH_KODI_CONNMAN}.unregister_websocket_callback", return_value=True
    ):
        await hass.async_stop()
