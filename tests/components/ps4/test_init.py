"""Tests for the PS4 Integration."""

from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.components import ps4
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    MediaType,
)
from homeassistant.components.ps4.const import (
    ATTR_MEDIA_IMAGE_URL,
    COMMANDS,
    CONFIG_ENTRY_VERSION as VERSION,
    DEFAULT_REGION,
    DOMAIN,
    PS4_DATA,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    ATTR_LOCKED,
    CONF_HOST,
    CONF_NAME,
    CONF_REGION,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import location as location_util

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.0.1"
MOCK_NAME = "test_ps4"
MOCK_REGION = "Some Region"
MOCK_CREDS = "1234567890A"

MOCK_DEVICE = {CONF_HOST: MOCK_HOST, CONF_NAME: MOCK_NAME, CONF_REGION: MOCK_REGION}

MOCK_DATA = {CONF_TOKEN: MOCK_CREDS, "devices": [MOCK_DEVICE]}

MOCK_FLOW_RESULT = {
    "version": VERSION,
    "minor_version": 1,
    "handler": DOMAIN,
    "type": FlowResultType.CREATE_ENTRY,
    "title": "test_ps4",
    "data": MOCK_DATA,
    "options": {},
    "subentries": (),
}

MOCK_ENTRY_ID = "SomeID"

MOCK_CONFIG = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA, entry_id=MOCK_ENTRY_ID)

MOCK_LOCATION = location_util.LocationInfo(
    "0.0.0.0",
    "US",
    "USD",
    "CA",
    "California",
    "San Diego",
    "92122",
    "America/Los_Angeles",
    32.8594,
    -117.2073,
    True,
)

MOCK_DEVICE_VERSION_1 = {
    CONF_HOST: MOCK_HOST,
    CONF_NAME: MOCK_NAME,
    CONF_REGION: "Some Region",
}

MOCK_DATA_VERSION_1 = {CONF_TOKEN: MOCK_CREDS, "devices": [MOCK_DEVICE_VERSION_1]}

MOCK_ENTRY_VERSION_1 = MockConfigEntry(
    domain=DOMAIN, data=MOCK_DATA_VERSION_1, entry_id=MOCK_ENTRY_ID, version=1
)

MOCK_UNIQUE_ID = "someuniqueid"

MOCK_ID = "CUSA00123"
MOCK_URL = "http://someurl.jpeg"
MOCK_TITLE = "Some Title"
MOCK_TYPE = MediaType.GAME

MOCK_GAMES_DATA_OLD_STR_FORMAT = {"mock_id": "mock_title", "mock_id2": "mock_title2"}

MOCK_GAMES_DATA = {
    ATTR_LOCKED: False,
    ATTR_MEDIA_CONTENT_TYPE: MediaType.GAME,
    ATTR_MEDIA_IMAGE_URL: MOCK_URL,
    ATTR_MEDIA_TITLE: MOCK_TITLE,
}

MOCK_GAMES_DATA_LOCKED = {
    ATTR_LOCKED: True,
    ATTR_MEDIA_CONTENT_TYPE: MediaType.GAME,
    ATTR_MEDIA_IMAGE_URL: MOCK_URL,
    ATTR_MEDIA_TITLE: MOCK_TITLE,
}

MOCK_GAMES = {MOCK_ID: MOCK_GAMES_DATA}
MOCK_GAMES_LOCKED = {MOCK_ID: MOCK_GAMES_DATA_LOCKED}


async def test_ps4_integration_setup(hass: HomeAssistant) -> None:
    """Test PS4 integration is setup."""
    await ps4.async_setup(hass, {})
    await hass.async_block_till_done()
    assert hass.data[PS4_DATA].protocol is not None


async def test_creating_entry_sets_up_media_player(hass: HomeAssistant) -> None:
    """Test setting up PS4 loads the media player."""
    mock_flow = "homeassistant.components.ps4.PlayStation4FlowHandler.async_step_user"
    with (
        patch(
            "homeassistant.components.ps4.media_player.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(mock_flow, return_value=MOCK_FLOW_RESULT),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_config_flow_entry_migrate(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that config flow entry is migrated correctly."""
    # Start with the config entry at Version 1.
    manager = hass.config_entries
    mock_entry = MOCK_ENTRY_VERSION_1
    mock_entry.add_to_manager(manager)
    mock_device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    mock_entity_id = f"media_player.ps4_{MOCK_UNIQUE_ID}"
    mock_e_entry = entity_registry.async_get_or_create(
        "media_player",
        "ps4",
        MOCK_UNIQUE_ID,
        config_entry=mock_entry,
        device_id=mock_device_entry.id,
    )
    assert len(entity_registry.entities) == 1
    assert mock_e_entry.entity_id == mock_entity_id
    assert mock_e_entry.unique_id == MOCK_UNIQUE_ID

    with (
        patch(
            "homeassistant.util.location.async_detect_location_info",
            return_value=MOCK_LOCATION,
        ),
        patch(
            "homeassistant.helpers.entity_registry.async_get",
            return_value=entity_registry,
        ),
    ):
        await ps4.async_migrate_entry(hass, mock_entry)

    await hass.async_block_till_done()

    assert len(entity_registry.entities) == 1
    for entity in entity_registry.entities.values():
        mock_entity = entity

    # Test that entity_id remains the same.
    assert mock_entity.entity_id == mock_entity_id
    assert mock_entity.device_id == mock_device_entry.id

    # Test that last four of credentials is appended to the unique_id.
    assert mock_entity.unique_id == f"{MOCK_UNIQUE_ID}_{MOCK_CREDS[-4:]}"

    # Test that config entry is at the current version.
    assert mock_entry.version == VERSION
    assert mock_entry.data[CONF_TOKEN] == MOCK_CREDS
    assert mock_entry.data["devices"][0][CONF_HOST] == MOCK_HOST
    assert mock_entry.data["devices"][0][CONF_NAME] == MOCK_NAME
    assert mock_entry.data["devices"][0][CONF_REGION] == DEFAULT_REGION


async def test_media_player_is_setup(hass: HomeAssistant) -> None:
    """Test media_player is setup correctly."""
    await setup_mock_component(hass)
    assert len(hass.data[PS4_DATA].devices) == 1


async def setup_mock_component(hass: HomeAssistant) -> None:
    """Set up Mock Media Player."""
    entry = MockConfigEntry(domain=ps4.DOMAIN, data=MOCK_DATA, version=VERSION)
    entry.add_to_manager(hass.config_entries)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


def test_games_reformat_to_dict(
    hass: HomeAssistant, patch_load_json_object: MagicMock
) -> None:
    """Test old data format is converted to new format."""
    patch_load_json_object.return_value = MOCK_GAMES_DATA_OLD_STR_FORMAT
    with (
        patch("homeassistant.components.ps4.save_json", side_effect=MagicMock()),
        patch("os.path.isfile", return_value=True),
    ):
        mock_games = ps4.load_games(hass, MOCK_ENTRY_ID)

    # New format is a nested dict.
    assert isinstance(mock_games, dict)
    assert mock_games["mock_id"][ATTR_MEDIA_TITLE] == "mock_title"
    assert mock_games["mock_id2"][ATTR_MEDIA_TITLE] == "mock_title2"
    for mock_game in mock_games:
        mock_data = mock_games[mock_game]
        assert isinstance(mock_data, dict)
        assert mock_data
        assert mock_data[ATTR_MEDIA_IMAGE_URL] is None
        assert mock_data[ATTR_LOCKED] is False
        assert mock_data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.GAME


def test_load_games(hass: HomeAssistant, patch_load_json_object: MagicMock) -> None:
    """Test that games are loaded correctly."""
    patch_load_json_object.return_value = MOCK_GAMES
    with (
        patch("homeassistant.components.ps4.save_json", side_effect=MagicMock()),
        patch("os.path.isfile", return_value=True),
    ):
        mock_games = ps4.load_games(hass, MOCK_ENTRY_ID)

    assert isinstance(mock_games, dict)

    mock_data = mock_games[MOCK_ID]
    assert isinstance(mock_data, dict)
    assert mock_data[ATTR_MEDIA_TITLE] == MOCK_TITLE
    assert mock_data[ATTR_MEDIA_IMAGE_URL] == MOCK_URL
    assert mock_data[ATTR_LOCKED] is False
    assert mock_data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.GAME


def test_loading_games_returns_dict(
    hass: HomeAssistant, patch_load_json_object: MagicMock
) -> None:
    """Test that loading games always returns a dict."""
    patch_load_json_object.side_effect = HomeAssistantError
    with (
        patch("homeassistant.components.ps4.save_json", side_effect=MagicMock()),
        patch("os.path.isfile", return_value=True),
    ):
        mock_games = ps4.load_games(hass, MOCK_ENTRY_ID)

    assert isinstance(mock_games, dict)
    assert not mock_games


async def test_send_command(hass: HomeAssistant) -> None:
    """Test send_command service."""
    await setup_mock_component(hass)

    mock_func = "homeassistant.components.ps4.media_player.PS4Device.async_send_command"

    mock_devices = hass.data[PS4_DATA].devices
    assert len(mock_devices) == 1
    mock_entity = mock_devices[0]
    assert mock_entity.entity_id == f"media_player.{MOCK_NAME}"

    # Test that all commands call service function.
    with patch(mock_func, return_value=True) as mock_service:
        for mock_command in COMMANDS:
            await hass.services.async_call(
                DOMAIN,
                "send_command",
                {ATTR_ENTITY_ID: mock_entity.entity_id, ATTR_COMMAND: mock_command},
            )
            await hass.async_block_till_done()
    assert len(mock_service.mock_calls) == len(COMMANDS)
