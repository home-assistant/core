"""Tests for the PS4 Integration."""
import os
import unittest
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_TITLE,
    MEDIA_TYPE_APP, MEDIA_TYPE_GAME)
from homeassistant.components import ps4
from homeassistant.components.ps4.const import (
    ATTR_MEDIA_IMAGE_URL, COMMANDS, CONFIG_ENTRY_VERSION as VERSION,
    DOMAIN, GAMES_FILE, PS4_DATA)
from homeassistant.const import (
    ATTR_COMMAND, ATTR_LOCKED, ATTR_ENTITY_ID, CONF_HOST,
    CONF_NAME, CONF_REGION, CONF_TOKEN)
from homeassistant.util.json import save_json
from homeassistant.setup import setup_component
from tests.common import (
    get_test_config_dir, get_test_home_assistant, MockConfigEntry, mock_coro)

MOCK_ID = 'CUSA00123'
MOCK_URL = 'http://someurl.jpeg'
MOCK_TITLE = 'Some Title'
MOCK_TYPE = MEDIA_TYPE_GAME

MOCK_GAMES_DATA_OLD_STR_FORMAT = {'mock_id': 'mock_title',
                                  'mock_id2': 'mock_title2'}

MOCK_GAMES_DATA = {
    ATTR_LOCKED: False,
    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_GAME,
    ATTR_MEDIA_IMAGE_URL: MOCK_URL,
    ATTR_MEDIA_TITLE: MOCK_TITLE}

MOCK_GAMES_DATA_LOCKED = {
    ATTR_LOCKED: True,
    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_GAME,
    ATTR_MEDIA_IMAGE_URL: MOCK_URL,
    ATTR_MEDIA_TITLE: MOCK_TITLE}

MOCK_GAMES = {MOCK_ID: MOCK_GAMES_DATA}
MOCK_GAMES_LOCKED = {MOCK_ID: MOCK_GAMES_DATA_LOCKED}

MOCK_HOST = '192.168.0.1'
MOCK_NAME = 'test_ps4'
MOCK_REGION = 'Some Region'
MOCK_CREDS = '1234567890A'
MOCK_PS4 = None

MOCK_DEVICE = {
    CONF_HOST: MOCK_HOST,
    CONF_NAME: MOCK_NAME,
    CONF_REGION: MOCK_REGION
}

MOCK_DATA = {
    CONF_TOKEN: MOCK_CREDS,
    'devices': [MOCK_DEVICE]
}

MOCK_FLOW_RESULT = {
    'version': VERSION, 'handler': DOMAIN,
    'type': data_entry_flow.RESULT_TYPE_CREATE_ENTRY,
    'title': 'test_ps4', 'data': MOCK_DATA
}

MOCK_ENTRY_ID = 'SomeID'

MOCK_CONFIG = MockConfigEntry(
    domain=DOMAIN, data=MOCK_DATA, entry_id=MOCK_ENTRY_ID)

MOCK_STATUS = {'running-app-titleid': 'CUSA00000',
               'host-type': 'PS4', 'host-ip': MOCK_HOST,
               'host-request-port': '997', 'host-id': 'MACADDRESS',
               'status_code': 200, 'host-name': 'FakePs4',
               'device-discovery-protocol-version': '00020020',
               'status': 'Ok', 'running-app-name': 'Random Game',
               'system-version': '06508011'}


async def test_ps4_integration_setup(hass):
    """Test PS4 integration is setup."""
    await ps4.async_setup(hass, {})
    await hass.async_block_till_done()
    assert hass.data[PS4_DATA].protocol is not None


async def test_creating_entry_sets_up_media_player(hass):
    """Test setting up PS4 loads the media player."""
    mock_flow =\
        'homeassistant.components.ps4.PlayStation4FlowHandler.async_step_user'
    with patch('homeassistant.components.ps4.media_player.async_setup_entry',
               return_value=mock_coro(True)) as mock_setup,\
            patch(mock_flow, return_value=mock_coro(MOCK_FLOW_RESULT)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_USER})
        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


class TestPS4MediaServices(unittest.TestCase):
    """Test services for PS4."""

    def cleanup(self):
        """Cleanup any data created from the tests."""
        if os.path.isfile(self.mock_file):
            os.remove(self.mock_file)

    def set_games_data(self, mock_data):
        """Set data in games file for tests."""
        save_json(self.mock_file, mock_data)
        self.hass.block_till_done()

    def setUp(self):
        """Setup test environment."""
        self.hass = get_test_home_assistant()
        self.hass.start()
        self.hass.block_till_done()
        self.mock_file = get_test_config_dir(GAMES_FILE)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()
        self.cleanup()

    def setup_mock_component(self):
        """Setup Mock Media Player."""
        entry = MockConfigEntry(
            domain=ps4.DOMAIN, data=MOCK_DATA, version=VERSION)
        entry.add_to_manager(self.hass.config_entries)
        setup_component(self.hass, DOMAIN, {DOMAIN: {}})
        self.hass.block_till_done()

    def test_media_player_is_setup(self):
        """Test media_player is setup correctly."""
        self.setup_mock_component()
        assert len(self.hass.data[PS4_DATA].devices) == 1

    def test_file_created_if_none(self):
        """Test that games file is created if it does not exist."""
        self.cleanup()
        mock_empty = ps4.load_games(self.hass)

        assert isinstance(mock_empty, dict)
        assert mock_empty is None
        assert self.mock_file == '{}/{}'.format(
            self.hass.config.path(), GAMES_FILE)

    def test_games_reformat_to_dict(self):
        """Test old data format is converted to new format."""
        self.set_games_data(MOCK_GAMES_DATA_OLD_STR_FORMAT)
        mock_games = ps4.load_games(self.hass)

        # New format is a nested dict.
        assert isinstance(mock_games, dict)
        assert mock_games['mock_id'][ATTR_MEDIA_TITLE] == 'mock_title'
        assert mock_games['mock_id2'][ATTR_MEDIA_TITLE] == 'mock_title2'
        for mock_game in mock_games:
            mock_data = mock_games[mock_game]
            assert isinstance(mock_data, dict)
            assert mock_data
            assert mock_data[ATTR_MEDIA_IMAGE_URL] is None
            assert mock_data[ATTR_LOCKED] is False
            assert mock_data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_GAME

    def test_load_games(self):
        """Test that games are loaded correctly."""
        self.set_games_data(MOCK_GAMES)
        mock_games = ps4.load_games(self.hass)
        assert isinstance(mock_games, dict)

        mock_data = mock_games[MOCK_ID]
        assert isinstance(mock_data, dict)
        assert mock_data[ATTR_MEDIA_TITLE] == MOCK_TITLE
        assert mock_data[ATTR_MEDIA_IMAGE_URL] == MOCK_URL
        assert mock_data[ATTR_LOCKED] is False
        assert mock_data[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_GAME

    def test_unlock_media(self):
        """Test that data is unlocked with unlock_media service."""
        self.setup_mock_component()
        self.set_games_data(MOCK_GAMES_LOCKED)
        mock_games = ps4.load_games(self.hass)
        assert mock_games[MOCK_ID][ATTR_LOCKED] is True
        self.hass.services.call(
            DOMAIN, 'unlock_media', {ATTR_MEDIA_CONTENT_ID: MOCK_ID})

        # Reload data again.
        mock_games = ps4.load_games(self.hass)

        assert mock_games[MOCK_ID][ATTR_LOCKED] is False

    def test_lock_media(self):
        """Test that data is locked with lock_media service."""
        self.setup_mock_component()
        self.set_games_data(MOCK_GAMES)
        mock_games = ps4.load_games(self.hass)
        assert mock_games[MOCK_ID][ATTR_LOCKED] is False
        self.hass.services.call(
            DOMAIN, 'lock_media', {ATTR_MEDIA_CONTENT_ID: MOCK_ID})
        mock_games = ps4.load_games(self.hass)
        assert mock_games[MOCK_ID][ATTR_LOCKED] is True

    def test_edit_media_title(self):
        """Test that title is edited with edit_media service."""
        self.setup_mock_component()
        self.set_games_data(MOCK_GAMES)
        mock_games = ps4.load_games(self.hass)

        # Test edit title.
        mock_title = 'some_new_title'
        assert mock_games[MOCK_ID][ATTR_LOCKED] is False
        assert mock_games[MOCK_ID][ATTR_MEDIA_TITLE] == MOCK_TITLE
        self.hass.services.call(
            DOMAIN, 'edit_media', {ATTR_MEDIA_CONTENT_ID: MOCK_ID,
                                   ATTR_MEDIA_TITLE: mock_title})
        mock_games = ps4.load_games(self.hass)
        # Locked attribute should be True now (data is locked).
        assert mock_games[MOCK_ID][ATTR_LOCKED] is True
        assert mock_games[MOCK_ID][ATTR_MEDIA_TITLE] == mock_title
        # Test that not specified attributes remain the same.
        assert mock_games[MOCK_ID][ATTR_MEDIA_IMAGE_URL] == MOCK_URL
        assert mock_games[MOCK_ID][ATTR_MEDIA_CONTENT_TYPE] ==\
            MEDIA_TYPE_GAME

    def test_edit_media_url(self):
        """Test that url is edited with edit_media service."""
        self.setup_mock_component()
        self.set_games_data(MOCK_GAMES)
        mock_games = ps4.load_games(self.hass)

        # Test edit url.
        mock_url = 'http://somenewurl'
        self.hass.services.call(
            DOMAIN, 'edit_media', {ATTR_MEDIA_CONTENT_ID: MOCK_ID,
                                   ATTR_MEDIA_IMAGE_URL: mock_url})

        mock_games = ps4.load_games(self.hass)
        # Locked attribute should be True now (data is locked).
        assert mock_games[MOCK_ID][ATTR_LOCKED] is True
        assert mock_games[MOCK_ID][ATTR_MEDIA_IMAGE_URL] == mock_url
        # Test that not specified attributes remain the same.
        assert mock_games[MOCK_ID][ATTR_MEDIA_TITLE] == MOCK_TITLE
        assert mock_games[MOCK_ID][ATTR_MEDIA_CONTENT_TYPE] ==\
            MOCK_TYPE

    def test_edit_media_type(self):
        """Test that media_type is edited with edit_media service."""
        self.setup_mock_component()
        self.set_games_data(MOCK_GAMES)
        mock_games = ps4.load_games(self.hass)

        # Test edit type.
        mock_type = MEDIA_TYPE_APP
        self.hass.services.call(
            DOMAIN, 'edit_media', {ATTR_MEDIA_CONTENT_ID: MOCK_ID,
                                   ATTR_MEDIA_CONTENT_TYPE: mock_type})
        mock_games = ps4.load_games(self.hass)

        # Locked attribute should be True now (data is locked).
        assert mock_games[MOCK_ID][ATTR_LOCKED] is True
        assert mock_games[MOCK_ID][ATTR_MEDIA_CONTENT_TYPE] ==\
            MEDIA_TYPE_APP
        # Test that not specified attributes remain the same.
        assert mock_games[MOCK_ID][ATTR_MEDIA_TITLE] == MOCK_TITLE
        assert mock_games[MOCK_ID][ATTR_MEDIA_IMAGE_URL] == MOCK_URL

    def test_edit_media_all(self):
        """Test that all data is edited with edit_media service."""
        self.setup_mock_component()
        self.set_games_data(MOCK_GAMES)
        mock_games = ps4.load_games(self.hass)
        mock_title = 'some_new_title'
        mock_url = 'http://somenewurl'
        mock_type = MEDIA_TYPE_APP

        # Edit all attributes.
        self.hass.services.call(
            DOMAIN, 'edit_media', {ATTR_MEDIA_CONTENT_ID: MOCK_ID,
                                   ATTR_MEDIA_TITLE: mock_title,
                                   ATTR_MEDIA_IMAGE_URL: mock_url,
                                   ATTR_MEDIA_CONTENT_TYPE: mock_type})
        mock_games = ps4.load_games(self.hass)

        assert mock_games[MOCK_ID][ATTR_LOCKED] is True
        assert mock_games[MOCK_ID][ATTR_MEDIA_CONTENT_TYPE] == mock_type
        assert mock_games[MOCK_ID][ATTR_MEDIA_TITLE] == mock_title
        assert mock_games[MOCK_ID][ATTR_MEDIA_IMAGE_URL] == mock_url

    def test_remove_media(self):
        """Test media entry is removed."""
        self.setup_mock_component()
        self.set_games_data(MOCK_GAMES)
        mock_games = ps4.load_games(self.hass)

        assert len(mock_games) == 1
        self.hass.services.call(
            DOMAIN, 'remove_media', {ATTR_MEDIA_CONTENT_ID: MOCK_ID})
        mock_games = ps4.load_games(self.hass)
        assert mock_games is None

    def test_add_media(self):
        """Test media entry is added."""
        self.setup_mock_component()
        self.set_games_data({})
        mock_games = ps4.load_games(self.hass)

        assert mock_games is None
        self.hass.services.call(
            DOMAIN, 'add_media', {ATTR_MEDIA_CONTENT_ID: MOCK_ID,
                                  ATTR_MEDIA_TITLE: MOCK_TITLE,
                                  ATTR_MEDIA_IMAGE_URL: MOCK_URL})

        mock_games = ps4.load_games(self.hass)
        assert len(mock_games) == 1
        assert MOCK_ID in mock_games
        assert mock_games[MOCK_ID][ATTR_LOCKED] is True
        assert mock_games[MOCK_ID][ATTR_MEDIA_TITLE] == MOCK_TITLE
        assert mock_games[MOCK_ID][ATTR_MEDIA_IMAGE_URL] == MOCK_URL
        # Defaults to MEDIA_TYPE_GAME if not specified.
        assert mock_games[MOCK_ID][ATTR_MEDIA_CONTENT_TYPE] == MOCK_TYPE

    def test_lock_current_media(self):
        """Test lock_current_media service."""
        mock_id1 = 'Mock_ID1'
        mock_id2 = 'Mock_ID2'
        mock_data = {mock_id1: MOCK_GAMES_DATA, mock_id2: MOCK_GAMES_DATA}

        self.setup_mock_component()
        self.set_games_data(mock_data)
        mock_games = ps4.load_games(self.hass)
        assert len(mock_games) == 2

        mock_devices = self.hass.data[PS4_DATA].devices
        assert len(mock_devices) == 1
        mock_entity = mock_devices[0]

        # Set media_id attr
        mock_entity._media_content_id = mock_id1  # noqa: pylint: disable=protected-access
        assert mock_entity.entity_id == 'media_player.{}'.format(MOCK_NAME)
        assert mock_games[mock_id1][ATTR_LOCKED] is False

        self.hass.services.call(
            DOMAIN, 'lock_current_media',
            {ATTR_ENTITY_ID: mock_entity.entity_id})

        mock_games = ps4.load_games(self.hass)
        assert mock_games[mock_id1][ATTR_LOCKED] is True
        # Ensure other data entry is unaffected.
        assert mock_games[mock_id2][ATTR_LOCKED] is False

    def test_unlock_current_media(self):
        """Test unlock_current_media service."""
        mock_id1 = 'Mock_ID1'
        mock_id2 = 'Mock_ID2'
        mock_data = {mock_id1: MOCK_GAMES_DATA_LOCKED,
                     mock_id2: MOCK_GAMES_DATA_LOCKED}

        self.setup_mock_component()
        self.set_games_data(mock_data)
        mock_games = ps4.load_games(self.hass)
        assert len(mock_games) == 2

        mock_devices = self.hass.data[PS4_DATA].devices
        assert len(mock_devices) == 1
        mock_entity = mock_devices[0]

        mock_entity._media_content_id = mock_id1  # noqa: pylint: disable=protected-access
        assert mock_entity.entity_id == 'media_player.{}'.format(MOCK_NAME)
        assert mock_games[mock_id1][ATTR_LOCKED] is True

        self.hass.services.call(
            DOMAIN, 'unlock_current_media',
            {ATTR_ENTITY_ID: mock_entity.entity_id})

        mock_games = ps4.load_games(self.hass)
        assert mock_games[mock_id1][ATTR_LOCKED] is False
        # Ensure other data entry is unaffected.
        assert mock_games[mock_id2][ATTR_LOCKED] is True

    def test_edit_current_media(self):
        """Test edit_current_media service."""
        mock_id1 = 'Mock_ID1'
        mock_id2 = 'Mock_ID2'
        mock_data = {mock_id1: MOCK_GAMES_DATA, mock_id2: MOCK_GAMES_DATA}

        self.setup_mock_component()
        self.set_games_data(mock_data)
        mock_games = ps4.load_games(self.hass)
        assert len(mock_games) == 2

        mock_devices = self.hass.data[PS4_DATA].devices
        assert len(mock_devices) == 1
        mock_entity = mock_devices[0]

        # Set media_id attr
        mock_entity._media_content_id = mock_id1  # noqa: pylint: disable=protected-access

        assert mock_entity.entity_id == 'media_player.{}'.format(MOCK_NAME)
        assert mock_id1 in mock_games
        assert mock_games[mock_id1][ATTR_LOCKED] is False
        assert mock_games[mock_id1][ATTR_MEDIA_TITLE] == MOCK_TITLE
        assert mock_games[mock_id1][ATTR_MEDIA_IMAGE_URL] == MOCK_URL
        assert mock_games[mock_id1][ATTR_MEDIA_CONTENT_TYPE] == MOCK_TYPE

        # Change the playing title only.
        mock_title = 'Some New Title'
        self.hass.services.call(
            DOMAIN, 'edit_current_media',
            {ATTR_ENTITY_ID: mock_entity.entity_id,
             ATTR_MEDIA_TITLE: mock_title})

        mock_games = ps4.load_games(self.hass)
        assert mock_games[mock_id1][ATTR_LOCKED] is True
        assert mock_games[mock_id1][ATTR_MEDIA_TITLE] == mock_title
        # Test that not specified attributes remain the same.
        assert mock_games[mock_id1][ATTR_MEDIA_IMAGE_URL] == MOCK_URL
        assert mock_games[mock_id1][ATTR_MEDIA_CONTENT_TYPE] == MOCK_TYPE

        # Ensure other data entry is unaffected.
        assert mock_games[mock_id2][ATTR_LOCKED] is False
        assert mock_games[mock_id2][ATTR_MEDIA_TITLE] == MOCK_TITLE
        assert mock_games[mock_id2][ATTR_MEDIA_IMAGE_URL] == MOCK_URL
        assert mock_games[mock_id2][ATTR_MEDIA_CONTENT_TYPE] == MOCK_TYPE

    def test_send_command(self):
        """Test send_command service."""
        self.setup_mock_component()
        mock_func = '{}{}'.format('homeassistant.components.ps4',
                                  '.media_player.PS4Device.async_send_command')

        mock_devices = self.hass.data[PS4_DATA].devices
        assert len(mock_devices) == 1
        mock_entity = mock_devices[0]
        assert mock_entity.entity_id == 'media_player.{}'.format(MOCK_NAME)

        # Test that all commands call service function.
        with patch(mock_func, return_value=mock_coro(True)) as mock_service:
            for mock_command in COMMANDS:
                self.hass.services.call(
                    DOMAIN, 'send_command',
                    {ATTR_ENTITY_ID: mock_entity.entity_id,
                     ATTR_COMMAND: mock_command})
                self.hass.block_till_done()

        assert len(mock_service.mock_calls) == len(COMMANDS)
