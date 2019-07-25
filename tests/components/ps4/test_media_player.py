"""Tests for the PS4 media player platform."""
from unittest.mock import MagicMock, patch

from pyps4_homeassistant.credential import get_ddp_message

from homeassistant.components import ps4
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE, ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE, MEDIA_TYPE_GAME)
from homeassistant.components.ps4.const import (
    ATTR_MEDIA_IMAGE_URL, CONFIG_ENTRY_VERSION as VERSION,
    DEFAULT_REGION, DOMAIN, GAMES_FILE, PS4_DATA)
from homeassistant.const import (
    ATTR_COMMAND, ATTR_ENTITY_ID, ATTR_LOCKED, CONF_HOST, CONF_NAME,
    CONF_REGION, CONF_TOKEN, STATE_IDLE, STATE_OFF, STATE_PLAYING,
    STATE_UNKNOWN)
from homeassistant.setup import async_setup_component
from tests.common import (
    MockConfigEntry, mock_device_registry, mock_registry, mock_coro)


MOCK_CREDS = '123412341234abcd12341234abcd12341234abcd12341234abcd12341234abcd'
MOCK_NAME = 'ha_ps4_name'
MOCK_REGION = DEFAULT_REGION
MOCK_GAMES_FILE = GAMES_FILE
MOCK_HOST = '192.168.0.2'
MOCK_HOST_NAME = 'Fake PS4'
MOCK_HOST_ID = 'A0000A0AA000'
MOCK_HOST_VERSION = '09879011'
MOCK_HOST_TYPE = 'PS4'
MOCK_STATUS_STANDBY = 'Server Standby'
MOCK_STATUS_ON = 'Ok'
MOCK_STANDBY_CODE = 620
MOCK_ON_CODE = 200
MOCK_TCP_PORT = 997
MOCK_DDP_PORT = 987
MOCK_DDP_VERSION = '00020020'
MOCK_RANDOM_PORT = '1234'

MOCK_TITLE_ID = 'CUSA00000'
MOCK_TITLE_NAME = 'Random Game'
MOCK_TITLE_TYPE = MEDIA_TYPE_GAME
MOCK_TITLE_ART_URL = 'https://somecoverurl'

MOCK_GAMES_DATA = {
    ATTR_LOCKED: False,
    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_GAME,
    ATTR_MEDIA_IMAGE_URL: MOCK_TITLE_ART_URL,
    ATTR_MEDIA_TITLE: MOCK_TITLE_NAME}

MOCK_GAMES_DATA_LOCKED = {
    ATTR_LOCKED: True,
    ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_GAME,
    ATTR_MEDIA_IMAGE_URL: MOCK_TITLE_ART_URL,
    ATTR_MEDIA_TITLE: MOCK_TITLE_NAME}

MOCK_STATUS_PLAYING = {
    'host-type': MOCK_HOST_TYPE,
    'host-ip': MOCK_HOST,
    'host-request-port': MOCK_TCP_PORT,
    'host-id': MOCK_HOST_ID,
    'host-name': MOCK_HOST_NAME,
    'running-app-titleid': MOCK_TITLE_ID,
    'running-app-name': MOCK_TITLE_NAME,
    'status': MOCK_STATUS_ON,
    'status_code': MOCK_ON_CODE,
    'device-discovery-protocol-version': MOCK_DDP_VERSION,
    'system-version': MOCK_HOST_VERSION}

MOCK_STATUS_IDLE = {
    'host-type': MOCK_HOST_TYPE,
    'host-ip': MOCK_HOST,
    'host-request-port': MOCK_TCP_PORT,
    'host-id': MOCK_HOST_ID,
    'host-name': MOCK_HOST_NAME,
    'status': MOCK_STATUS_ON,
    'status_code': MOCK_ON_CODE,
    'device-discovery-protocol-version': MOCK_DDP_VERSION,
    'system-version': MOCK_HOST_VERSION}

MOCK_STATUS_STANDBY = {
    'host-type': MOCK_HOST_TYPE,
    'host-ip': MOCK_HOST,
    'host-request-port': MOCK_TCP_PORT,
    'host-id': MOCK_HOST_ID,
    'host-name': MOCK_HOST_NAME,
    'status': MOCK_STATUS_STANDBY,
    'status_code': MOCK_STANDBY_CODE,
    'device-discovery-protocol-version': MOCK_DDP_VERSION,
    'system-version': MOCK_HOST_VERSION}

MOCK_STATUS_OFF = None

MOCK_DEVICE = {
    CONF_HOST: MOCK_HOST,
    CONF_NAME: MOCK_NAME,
    CONF_REGION: MOCK_REGION
}

MOCK_ENTRY_ID = 'SomeID'

MOCK_DEVICE_MODEL = 'PlayStation 4'

MOCK_DATA = {
    CONF_TOKEN: MOCK_CREDS,
    'devices': [MOCK_DEVICE]
}

MOCK_CONFIG = MockConfigEntry(
    domain=DOMAIN, data=MOCK_DATA, entry_id=MOCK_ENTRY_ID)

MOCK_LOAD = 'homeassistant.components.ps4.media_player.load_games'
MOCK_SAVE = 'homeassistant.components.ps4.save_json'


async def setup_mock_component(hass, entry=None):
    """Set up Mock Media Player."""
    if entry is None:
        mock_entry = MockConfigEntry(
            domain=ps4.DOMAIN, data=MOCK_DATA, version=VERSION,
            entry_id=MOCK_ENTRY_ID)
    else:
        mock_entry = entry

    mock_entry.add_to_hass(hass)

    # Don't use an actual file.
    with patch(MOCK_LOAD, return_value={}),\
            patch(MOCK_SAVE, side_effect=MagicMock()):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    mock_entities = hass.states.async_entity_ids()

    mock_entity_id = mock_entities[0]

    return mock_entity_id


async def mock_parse_status(hass, mock_device, load_data):
    """Parse entity status with patched load_json."""
    # Don't use an actual file.
    with patch(MOCK_LOAD, return_value=load_data),\
            patch(MOCK_SAVE, side_effect=MagicMock()),\
            patch('os.path.isfile', return_value=True):
        mock_device._parse_status()  # noqa: pylint: disable=protected-access
        mock_device.schedule_update_ha_state()
        await hass.async_block_till_done()


def mock_ps4_status(hass, mock_device, mock_status):
    """Set the status for a Mock PS4."""
    mock_device._ps4.status = mock_status  # noqa: pylint: disable=protected-access


def mock_ps4_device(hass, mock_device):
    """Return mock ps4 object."""
    return mock_device._ps4  # noqa: pylint: disable=protected-access


async def test_media_player_is_setup_correctly_with_entry(hass):
    """Test entity is setup correctly with entry correctly."""
    mock_entity_id = await setup_mock_component(hass)
    mock_state = hass.states.get(mock_entity_id).state

    # Assert status updated callback is added to protocol.
    assert len(hass.data[PS4_DATA].protocol.callbacks) == 1

    # Test that entity is added to hass.
    assert hass.data[PS4_DATA].protocol is not None
    assert mock_entity_id == 'media_player.{}'.format(MOCK_NAME)
    assert mock_state == STATE_UNKNOWN


async def test_state_off_is_set(hass):
    """Test that state is set to off."""
    mock_entity_id = await setup_mock_component(hass)

    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4_status(hass, mock_device, MOCK_STATUS_STANDBY)

    await mock_parse_status(hass, mock_device, {})

    assert hass.states.get(mock_entity_id).state == STATE_OFF


async def test_state_playing_is_set(hass):
    """Test that state is set to idle."""
    mock_entity_id = await setup_mock_component(hass)

    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4_status(hass, mock_device, MOCK_STATUS_PLAYING)

    with patch.object(mock_device, 'async_get_title_data',
                      return_value=mock_coro(None)):
        await mock_parse_status(hass, mock_device, {})

    assert hass.states.get(mock_entity_id).state == STATE_PLAYING


async def test_state_idle_is_set(hass):
    """Test that state is set to idle."""
    mock_entity_id = await setup_mock_component(hass)

    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4_status(hass, mock_device, MOCK_STATUS_IDLE)

    await mock_parse_status(hass, mock_device, {})

    assert hass.states.get(mock_entity_id).state == STATE_IDLE


async def test_state_none_is_set(hass):
    """Test that state is set to None."""
    mock_entity_id = await setup_mock_component(hass)

    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4_status(hass, mock_device, None)

    await mock_parse_status(hass, mock_device, {})

    assert hass.states.get(mock_entity_id).state == STATE_UNKNOWN


async def test_state_set_with_protocol_callback(hass):
    """Test that state is set with protocol callback."""
    mock_entity_id = await setup_mock_component(hass)
    mock_protocol = hass.data[PS4_DATA].protocol

    # Mock raw UDP response from device.
    mock_response = get_ddp_message(MOCK_STATUS_STANDBY).encode()

    with patch(MOCK_LOAD, side_effect=MagicMock()),\
            patch(MOCK_SAVE, side_effect=MagicMock()):
        mock_protocol.datagram_received(
            mock_response, (MOCK_HOST, MOCK_RANDOM_PORT))
        await hass.async_block_till_done()

    assert hass.states.get(mock_entity_id).state == STATE_OFF


async def test_media_attributes_are_fetched(hass):
    """Test that media attributes are fetched."""
    mock_entity_id = await setup_mock_component(hass)

    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4_status(hass, mock_device, MOCK_STATUS_PLAYING)
    mock_ps4 = mock_ps4_device(hass, mock_device)
    assert not mock_device.source_list

    # Mock result from fetching data.
    mock_result = MagicMock()
    mock_result.name = MOCK_TITLE_NAME
    mock_result.cover_art = MOCK_TITLE_ART_URL
    mock_result.game_type = 'game'

    with patch.object(
            mock_ps4, 'async_get_ps_store_data',
            return_value=mock_coro(mock_result)) as mock_fetch,\
            patch(MOCK_SAVE, side_effect=MagicMock()):

        await mock_parse_status(hass, mock_device, {})

    mock_state = hass.states.get(mock_entity_id).state

    assert len(mock_fetch.mock_calls) == 1

    assert mock_state == STATE_PLAYING

    assert mock_device.media_content_id == MOCK_TITLE_ID
    assert mock_device.media_title == MOCK_TITLE_NAME
    assert mock_device.media_image_url == MOCK_TITLE_ART_URL
    assert mock_device.media_content_type == MOCK_TITLE_TYPE


async def test_media_attributes_are_loaded(hass):
    """Test that media attributes are loaded."""
    mock_entity_id = await setup_mock_component(hass)

    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4_status(hass, mock_device, MOCK_STATUS_PLAYING)
    mock_ps4 = mock_ps4_device(hass, mock_device)
    assert not mock_device.source_list

    mock_data = {MOCK_TITLE_ID: MOCK_GAMES_DATA_LOCKED}

    with patch.object(
            mock_ps4, 'async_get_ps_store_data',
            return_value=mock_coro(None)) as mock_fetch:
        await mock_parse_status(hass, mock_device, mock_data)

    mock_state = hass.states.get(mock_entity_id).state

    # Ensure that data is not fetched.
    assert not mock_fetch.mock_calls

    assert mock_state == STATE_PLAYING

    assert len(mock_device.source_list) == 1
    assert mock_device.source_list[0] == MOCK_TITLE_NAME
    assert mock_device.media_content_id == MOCK_TITLE_ID
    assert mock_device.media_title == MOCK_TITLE_NAME
    assert mock_device.media_image_url == MOCK_TITLE_ART_URL
    assert mock_device.media_content_type == MOCK_TITLE_TYPE


async def test_device_info_is_set_from_status_correctly(hass):
    """Test that device info is set correctly from status update."""
    mock_entity_id = await setup_mock_component(hass)
    mock_device = hass.data[PS4_DATA].devices[0]
    mock_status = MOCK_STATUS_STANDBY
    mock_ps4_status(hass, mock_device, MOCK_STATUS_STANDBY)

    await mock_device.async_get_device_info(mock_status)
    await mock_parse_status(hass, mock_device, {})

    # Reformat mock status-sw_version for assertion.
    mock_version = mock_status['system-version']
    mock_version = mock_version[1:4]
    mock_version = "{}.{}".format(mock_version[0], mock_version[1:])

    mock_state = hass.states.get(mock_entity_id).state

    assert mock_state == STATE_OFF

    assert mock_device.device_info is not None
    assert mock_device.device_info['name'] == MOCK_HOST_NAME
    assert mock_device.device_info['model'] == MOCK_DEVICE_MODEL
    assert mock_device.device_info['sw_version'] == mock_version
    assert mock_device.device_info['identifiers'] == {
        (DOMAIN, mock_status['host-id'])}


async def test_device_info_is_assummed(hass):
    """Test that device info is assumed if device is unavailable."""
    # Create a device registry entry with device info.
    mock_d_registry = mock_device_registry(hass)
    mock_d_registry.async_get_or_create(
        config_entry_id=MOCK_ENTRY_ID, name=MOCK_HOST_NAME,
        model=MOCK_DEVICE_MODEL, identifiers={(DOMAIN, MOCK_HOST_ID)},
        sw_version=MOCK_HOST_VERSION)
    mock_d_entries = mock_d_registry.devices
    assert len(mock_d_entries) == 1

    # Create a entity_registry entry which is using identifiers from device.
    mock_unique_id = ps4.format_unique_id(MOCK_CREDS, MOCK_HOST_ID)
    mock_e_registry = mock_registry(hass)
    mock_e_registry.async_get_or_create(
        'media_player', DOMAIN, mock_unique_id, config_entry_id=MOCK_ENTRY_ID)
    mock_entity_id = mock_e_registry.async_get_entity_id(
        'media_player', DOMAIN, mock_unique_id)

    mock_entity_id = await setup_mock_component(hass)

    mock_device = hass.data[PS4_DATA].devices[0]
    mock_state = hass.states.get(mock_entity_id).state

    # Ensure that state is not set.
    assert mock_state == STATE_UNKNOWN

    # Ensure that entity_id is the same as the existing.
    mock_entities = hass.states.async_entity_ids()
    assert len(mock_entities) == 1
    assert mock_entities[0] == mock_entity_id

    # With no state/status, info should be set from registry entry.
    assert mock_device.device_info is not None
    assert mock_device.device_info['name'] == MOCK_HOST_NAME
    assert mock_device.device_info['model'] == MOCK_DEVICE_MODEL
    assert mock_device.device_info['identifiers'] == {(DOMAIN, MOCK_HOST_ID)}
    assert mock_device.device_info['sw_version'] == MOCK_HOST_VERSION


async def test_device_info_assummed_works(hass):
    """Reverse test that device info assumption works."""
    mock_entity_id = await setup_mock_component(hass)

    mock_device = hass.data[PS4_DATA].devices[0]
    mock_state = hass.states.get(mock_entity_id).state

    # Ensure that state is not set.
    assert mock_state == STATE_UNKNOWN

    # With no state/status and no registry entries, info should be None.
    assert mock_device.device_info is None


async def test_turn_on(hass):
    """Test that turn on service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4 = mock_ps4_device(hass, mock_device)

    with patch.object(
            mock_ps4, 'wakeup',
            return_value=MagicMock()) as mock_func:

        await hass.services.async_call(
            'media_player', 'turn_on',
            {ATTR_ENTITY_ID: mock_entity_id})
        await hass.async_block_till_done()

    assert len(mock_func.mock_calls) == 1


async def test_turn_off(hass):
    """Test that turn off service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4 = mock_ps4_device(hass, mock_device)

    with patch.object(
            mock_ps4, 'standby',
            return_value=mock_coro()) as mock_func:

        await hass.services.async_call(
            'media_player', 'turn_off',
            {ATTR_ENTITY_ID: mock_entity_id})
        await hass.async_block_till_done()

    assert len(mock_func.mock_calls) == 1


async def test_media_pause(hass):
    """Test that media pause service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4 = mock_ps4_device(hass, mock_device)

    with patch.object(
            mock_ps4, 'remote_control',
            return_value=mock_coro()) as mock_func:

        await hass.services.async_call(
            'media_player', 'media_pause',
            {ATTR_ENTITY_ID: mock_entity_id})
        await hass.async_block_till_done()

    assert len(mock_func.mock_calls) == 1


async def test_media_stop(hass):
    """Test that media stop service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4 = mock_ps4_device(hass, mock_device)

    with patch.object(
            mock_ps4, 'remote_control',
            return_value=mock_coro()) as mock_func:

        await hass.services.async_call(
            'media_player', 'media_stop',
            {ATTR_ENTITY_ID: mock_entity_id})
        await hass.async_block_till_done()

    assert len(mock_func.mock_calls) == 1


async def test_select_source(hass):
    """Test that select source service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4 = mock_ps4_device(hass, mock_device)
    mock_device._games = {MOCK_TITLE_ID: MOCK_GAMES_DATA}  # noqa: pylint: disable=protected-access

    with patch.object(
            mock_ps4, 'start_title',
            return_value=mock_coro()) as mock_func:

        # Test with title name.
        await hass.services.async_call(
            'media_player', 'select_source',
            {ATTR_ENTITY_ID: mock_entity_id,
             ATTR_INPUT_SOURCE: MOCK_TITLE_NAME})

        # Test with title name in caps.
        await hass.services.async_call(
            'media_player', 'select_source',
            {ATTR_ENTITY_ID: mock_entity_id,
             ATTR_INPUT_SOURCE: MOCK_TITLE_NAME.upper()})

        # Test with title ID.
        await hass.services.async_call(
            'media_player', 'select_source',
            {ATTR_ENTITY_ID: mock_entity_id,
             ATTR_INPUT_SOURCE: MOCK_TITLE_ID})
        await hass.async_block_till_done()

    assert len(mock_func.mock_calls) == 3


async def test_ps4_send_command(hass):
    """Test that ps4 send command service calls function."""
    mock_entity_id = await setup_mock_component(hass)
    mock_device = hass.data[PS4_DATA].devices[0]
    mock_ps4 = mock_ps4_device(hass, mock_device)

    with patch.object(
            mock_ps4, 'remote_control',
            return_value=mock_coro()) as mock_func:

        await hass.services.async_call(
            DOMAIN, 'send_command',
            {ATTR_ENTITY_ID: mock_entity_id,
             ATTR_COMMAND: 'ps'})
        await hass.async_block_till_done()

    assert len(mock_func.mock_calls) == 1


async def test_entry_is_unloaded(hass):
    """Test that entry is unloaded."""
    mock_entry = MockConfigEntry(
        domain=ps4.DOMAIN, data=MOCK_DATA, version=VERSION,
        entry_id=MOCK_ENTRY_ID)
    await setup_mock_component(hass, mock_entry)
    mock_unload = await ps4.async_unload_entry(hass, mock_entry)

    assert mock_unload is True
    assert not hass.data[PS4_DATA].devices

    # Test that callback listener for entity is removed from protocol.
    assert not hass.data[PS4_DATA].protocol.callbacks
