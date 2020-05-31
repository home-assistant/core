"""Tests for the arcam_fmj component."""
from arcam.fmj.client import Client
from arcam.fmj.state import State
import pytest

from homeassistant.components.arcam_fmj import DEVICE_SCHEMA
from homeassistant.components.arcam_fmj.const import DOMAIN
from homeassistant.components.arcam_fmj.media_player import ArcamFmj
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, patch

MOCK_HOST = "127.0.0.1"
MOCK_PORT = 1234
MOCK_TURN_ON = {
    "service": "switch.turn_on",
    "data": {"entity_id": "switch.test"},
}
MOCK_NAME = "dummy"
MOCK_UUID = "1234"
MOCK_ENTITY_ID = "media_player.arcam_fmj_127_0_0_1_1234_1"
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


@pytest.fixture(name="state_1")
def state_1_fixture(client):
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


@pytest.fixture(name="state_2")
def state_2_fixture(client):
    """Get a mocked state."""
    state = Mock(State)
    state.client = client
    state.zn = 2
    state.get_power.return_value = True
    state.get_volume.return_value = 0.0
    state.get_source_list.return_value = []
    state.get_incoming_audio_format.return_value = (0, 0)
    state.get_mute.return_value = None
    return state


@pytest.fixture(name="state")
def state_fixture(state_1):
    """Get a mocked state."""
    return state_1


@pytest.fixture(name="player")
def player_fixture(hass, state):
    """Get standard player."""
    player = ArcamFmj(state, MOCK_UUID, MOCK_NAME, None)
    player.entity_id = MOCK_ENTITY_ID
    player.hass = hass
    player.async_write_ha_state = Mock()
    return player


@pytest.fixture(name="player_setup")
async def player_setup_fixture(hass, config, state_1, state_2, client):
    """Get standard player."""

    def state_mock(cli, zone):
        if zone == 1:
            return state_1
        if zone == 2:
            return state_2

    with patch("homeassistant.components.arcam_fmj.Client", return_value=client), patch(
        "homeassistant.components.arcam_fmj.media_player.State", side_effect=state_mock
    ), patch("homeassistant.components.arcam_fmj._run_client", return_value=None):
        assert await async_setup_component(hass, "arcam_fmj", config)
        await hass.async_block_till_done()
        yield MOCK_ENTITY_ID
