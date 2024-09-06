"""Test squeezebox binary sensors."""

import copy
from unittest.mock import patch

from homeassistant.components.squeezebox.const import (
    STATUS_QUERY_LIBRARYNAME,
    STATUS_QUERY_MAC,
    STATUS_QUERY_UUID,
    STATUS_QUERY_VERSION,
    STATUS_SENSOR_RESCAN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import configure_squeezebox

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
    STATUS_QUERY_LIBRARYNAME: "FakeLib",
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


async def test_binary_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lms: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor states and attributes."""

    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.BINARY_SENSOR],
        ),
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=copy.deepcopy(FAKE_QUERY_RESPONSE),
        ),
    ):
        await configure_squeezebox(hass, config_entry, lms)

    state = hass.states.get("binary_sensor.1_2_3_4_needs_restart")

    assert state is not None
    assert state.state == "off"
