"""Configuration for HEOS tests."""
from asynctest.mock import Mock, patch as patch
from pyheos import Dispatcher, HeosPlayer, const
import pytest

from homeassistant.components.heos import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock HEOS config entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: '127.0.0.1'},
                           title='Controller (127.0.0.1)')


@pytest.fixture(name="controller")
def controller_fixture(players):
    """Create a mock Heos controller fixture."""
    with patch("pyheos.Heos", autospec=True) as mock:
        mock_heos = mock.return_value
        mock_heos.get_players.return_value = players
        mock_heos.players = players
        yield mock_heos


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {
        DOMAIN: {CONF_HOST: '127.0.0.1'}
    }


@pytest.fixture(name="players")
def player_fixture():
    """Create a mock HeosPlayer."""
    player = Mock(HeosPlayer, autospec=True)
    player.heos.dispatcher = Dispatcher()
    player.player_id = 1
    player.name = "Test Player"
    player.model = "Test Model"
    player.version = "1.0.0"
    player.is_muted = False
    player.available = True
    player.state = const.PLAY_STATE_STOP
    player.ip_address = "127.0.0.1"
    player.network = "wired"
    player.shuffle = False
    player.repeat = const.REPEAT_OFF
    player.volume = 25
    player.now_playing_media.supported_controls = const.CONTROLS_ALL
    player.now_playing_media.album_id = 1
    player.now_playing_media.queue_id = 1
    player.now_playing_media.source_id = 1
    player.now_playing_media.station = "Station Name"
    player.now_playing_media.type = "Station"
    player.now_playing_media.album = "Album"
    player.now_playing_media.artist = "Artist"
    player.now_playing_media.media_id = "1"
    player.now_playing_media.duration = None
    player.now_playing_media.current_position = None
    player.now_playing_media.image_url = "http://"
    player.now_playing_media.song = "Song"
    return {player.player_id: player}
