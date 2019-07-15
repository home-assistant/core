"""Tests for the PS4 Integration."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ps4
from homeassistant.components.ps4.const import (
    COMMANDS, CONFIG_ENTRY_VERSION as VERSION,
    DEFAULT_REGION, DOMAIN, PS4_DATA)
from homeassistant.const import (
    ATTR_COMMAND, ATTR_ENTITY_ID, CONF_HOST,
    CONF_NAME, CONF_REGION, CONF_TOKEN)
from homeassistant.util import location
from homeassistant.setup import async_setup_component
from tests.common import (MockConfigEntry, mock_coro, mock_registry)

MOCK_HOST = '192.168.0.1'
MOCK_NAME = 'test_ps4'
MOCK_REGION = 'Some Region'
MOCK_CREDS = '1234567890A'

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

MOCK_LOCATION = location.LocationInfo(
    '0.0.0.0', 'US', 'United States', 'CA', 'California',
    'San Diego', '92122', 'America/Los_Angeles', 32.8594,
    -117.2073, True)

MOCK_DEVICE_VERSION_1 = {
    CONF_HOST: MOCK_HOST,
    CONF_NAME: MOCK_NAME,
    CONF_REGION: "Some Region"
}

MOCK_DATA_VERSION_1 = {
    CONF_TOKEN: MOCK_CREDS,
    'devices': [MOCK_DEVICE_VERSION_1]
}

MOCK_DEVICE_ID = 'somedeviceid'

MOCK_ENTRY_VERSION_1 = MockConfigEntry(
    domain=DOMAIN, data=MOCK_DATA_VERSION_1, entry_id=MOCK_ENTRY_ID, version=1)

MOCK_UNIQUE_ID = 'someuniqueid'


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


async def test_config_flow_entry_migrate(hass):
    """Test that config flow entry is migrated correctly."""
    # Start with the config entry at Version 1.
    manager = hass.config_entries
    mock_entry = MOCK_ENTRY_VERSION_1
    mock_entry.add_to_manager(manager)
    mock_e_registry = mock_registry(hass)
    mock_entity_id = 'media_player.ps4_{}'.format(
        MOCK_UNIQUE_ID)
    mock_e_entry = mock_e_registry.async_get_or_create(
        'media_player', 'ps4', MOCK_UNIQUE_ID, config_entry_id=MOCK_ENTRY_ID,
        device_id=MOCK_DEVICE_ID)
    assert len(mock_e_registry.entities) == 1
    assert mock_e_entry.entity_id == mock_entity_id
    assert mock_e_entry.unique_id == MOCK_UNIQUE_ID

    with patch('homeassistant.util.location.async_detect_location_info',
               return_value=mock_coro(MOCK_LOCATION)), \
            patch('homeassistant.helpers.entity_registry.async_get_registry',
                  return_value=mock_coro(mock_e_registry)):
        await ps4.async_migrate_entry(hass, mock_entry)

    await hass.async_block_till_done()

    assert len(mock_e_registry.entities) == 1
    for entity in mock_e_registry.entities.values():
        mock_entity = entity

    # Test that entity_id remains the same.
    assert mock_entity.entity_id == mock_entity_id
    assert mock_entity.device_id == MOCK_DEVICE_ID

    # Test that last four of credentials is appended to the unique_id.
    assert mock_entity.unique_id == '{}_{}'.format(
        MOCK_UNIQUE_ID, MOCK_CREDS[-4:])

    # Test that config entry is at the current version.
    assert mock_entry.version == VERSION
    assert mock_entry.data[CONF_TOKEN] == MOCK_CREDS
    assert mock_entry.data['devices'][0][CONF_HOST] == MOCK_HOST
    assert mock_entry.data['devices'][0][CONF_NAME] == MOCK_NAME
    assert mock_entry.data['devices'][0][CONF_REGION] ==\
        DEFAULT_REGION


async def test_media_player_is_setup(hass):
    """Test media_player is setup correctly."""
    await setup_mock_component(hass)
    assert len(hass.data[PS4_DATA].devices) == 1


async def setup_mock_component(hass):
    """Set up Mock Media Player."""
    entry = MockConfigEntry(
        domain=ps4.DOMAIN, data=MOCK_DATA, version=VERSION)
    entry.add_to_manager(hass.config_entries)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_send_command(hass):
    """Test send_command service."""
    await setup_mock_component(hass)

    mock_func = '{}{}'.format('homeassistant.components.ps4',
                              '.media_player.PS4Device.async_send_command')

    mock_devices = hass.data[PS4_DATA].devices
    assert len(mock_devices) == 1
    mock_entity = mock_devices[0]
    assert mock_entity.entity_id == 'media_player.{}'.format(MOCK_NAME)

    # Test that all commands call service function.
    with patch(mock_func, return_value=mock_coro(True)) as mock_service:
        for mock_command in COMMANDS:
            await hass.services.async_call(
                DOMAIN, 'send_command',
                {ATTR_ENTITY_ID: mock_entity.entity_id,
                 ATTR_COMMAND: mock_command})
            await hass.async_block_till_done()
    assert len(mock_service.mock_calls) == len(COMMANDS)
