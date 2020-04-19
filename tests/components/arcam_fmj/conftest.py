"""Tests for the arcam_fmj component."""
from arcam.fmj.client import Client
from arcam.fmj.state import State
from asynctest import Mock
import pytest

from homeassistant.components.arcam_fmj import DEVICE_SCHEMA
from homeassistant.components.arcam_fmj.const import DOMAIN
from homeassistant.components.arcam_fmj.media_player import ArcamFmj
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 1234
MOCK_TURN_ON = {
    "service": "switch.turn_on",
    "data": {"entity_id": "switch.test"},
}
MOCK_NAME = "dummy"
MOCK_ENTITY_ID = "media_player.arcam_fmj_1"
MOCK_CONFIG = DEVICE_SCHEMA({CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT})


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: [{CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT}]}


@pytest.fixture(name="client")
def client_fixture():
    """Get a mocked client."""
    client = Mock(Client)
    client.host = MOCK_HOST
    client.port = MOCK_PORT
    return client


@pytest.fixture(name="state")
def state_fixture(client):
    """Get a mocked state."""
    state = Mock(State)
    state.client = client
    state.zn = 1
    state.get_power.return_value = True
    state.get_volume.return_value = 0.0
    state.get_source_list.return_value = []
    state.get_incoming_audio_format.return_value = (0, 0)
    state.get_mute.return_value = None
    return state


@pytest.fixture(name="player")
def player_fixture(hass, state):
    """Get standard player."""
    player = ArcamFmj(state, MOCK_NAME, None)
    player.entity_id = MOCK_ENTITY_ID
    player.hass = hass
    player.async_write_ha_state = Mock()
    return player
