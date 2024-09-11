"""Tests for the Logitech Squeezebox integration."""

from homeassistant.components.squeezebox.const import (
    DOMAIN,
    STATUS_QUERY_LIBRARYNAME,
    STATUS_QUERY_MAC,
    STATUS_QUERY_UUID,
    STATUS_QUERY_VERSION,
    STATUS_SENSOR_INFO_TOTAL_ALBUMS,
    STATUS_SENSOR_INFO_TOTAL_ARTISTS,
    STATUS_SENSOR_INFO_TOTAL_DURATION,
    STATUS_SENSOR_INFO_TOTAL_GENRES,
    STATUS_SENSOR_INFO_TOTAL_SONGS,
    STATUS_SENSOR_LASTSCAN,
    STATUS_SENSOR_OTHER_PLAYER_COUNT,
    STATUS_SENSOR_PLAYER_COUNT,
    STATUS_SENSOR_RESCAN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

# from homeassistant.setup import async_setup_component
from tests.common import MockConfigEntry

FAKE_IP = "42.42.42.42"
FAKE_MAC = "deadbeefdead"
FAKE_UUID = "deadbeefdeadbeefbeefdeafbeef42"
FAKE_PORT = 9000
FAKE_VERSION = "42.0"

FAKE_QUERY_RESPONSE = {
    STATUS_QUERY_UUID: FAKE_UUID,
    STATUS_QUERY_MAC: FAKE_MAC,
    STATUS_QUERY_VERSION: FAKE_VERSION,
    STATUS_SENSOR_RESCAN: 1,
    STATUS_SENSOR_LASTSCAN: 0,
    STATUS_QUERY_LIBRARYNAME: "FakeLib",
    STATUS_SENSOR_INFO_TOTAL_ALBUMS: 4,
    STATUS_SENSOR_INFO_TOTAL_ARTISTS: 2,
    STATUS_SENSOR_INFO_TOTAL_DURATION: 500,
    STATUS_SENSOR_INFO_TOTAL_GENRES: 1,
    STATUS_SENSOR_INFO_TOTAL_SONGS: 42,
    STATUS_SENSOR_PLAYER_COUNT: 10,
    STATUS_SENSOR_OTHER_PLAYER_COUNT: 0,
    "players_loop": [
        {
            "isplaying": 0,
            "name": "SqueezeLite-HA-Addon",
            "seq_no": 0,
            "modelname": "SqueezeLite-HA-Addon",
            "playerindex": "status",
            "model": "squeezelite",
            "uuid": FAKE_UUID,
            "canpoweroff": 1,
            "ip": "192.168.78.86:57700",
            "displaytype": "none",
            "playerid": "f9:23:cd:37:c5:ff",
            "power": 0,
            "isplayer": 1,
            "connected": 1,
            "firmware": "v2.0.0-1488",
        }
    ],
    "count": 1,
}


async def setup_mocked_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock ConfigEntry in Home Assistant."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_UUID,
        data={
            CONF_HOST: FAKE_IP,
            CONF_PORT: FAKE_PORT,
        },
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
