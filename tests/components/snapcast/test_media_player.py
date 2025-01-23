"""Test the snapcast media player implementation."""

from typing import Any
from unittest.mock import patch

from snapcast.control.server import CONTROL_PORT

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.components.snapcast.const import DOMAIN, DOMAIN as SNAPCAST_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_PLAYING
from homeassistant.core import HomeAssistant

from .const import TEST_CLIENT_ENTITY_ID, TEST_GROUP_ENTITY_ID, TEST_STATE

from tests.common import MockConfigEntry


async def _call_service(hass: HomeAssistant, name: str, data: dict[str, Any]) -> None:
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, name, service_data=data, blocking=True
    )


async def _setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with a mock config entry."""

    # Create a mock config entry
    mock_config_entry = MockConfigEntry(
        domain=SNAPCAST_DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: CONTROL_PORT,
        },
    )

    # Patch Snapserver to prevent connection attempts
    with (
        patch("snapcast.control.server.Snapserver.start"),
        patch("snapcast.control.server.Snapserver._request"),
    ):
        # Add mock config entry to HASS and setup integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    return mock_config_entry


async def test_state(
    hass: HomeAssistant,
) -> None:
    """Test basic state information."""

    # Setup the integration
    mock_config_entry = await _setup_integration(hass)
    assert mock_config_entry

    # Fetch the coordinator
    coordinator = hass.data[SNAPCAST_DOMAIN][mock_config_entry.entry_id]

    # Load the test server data manually
    coordinator.server._on_server_update(TEST_STATE)

    # Asset basic state matches in both client and group entities
    for entity_id in [TEST_CLIENT_ENTITY_ID, TEST_GROUP_ENTITY_ID]:
        state = hass.states.get(entity_id)
        assert state

        assert state.state == STATE_PLAYING
        assert state.attributes.get(ATTR_MEDIA_VOLUME_MUTED) is False
        assert state.attributes.get(ATTR_MEDIA_VOLUME_LEVEL) == 0.48
        assert state.attributes.get(ATTR_INPUT_SOURCE) == "test_stream_1"
        assert state.attributes.get(ATTR_INPUT_SOURCE_LIST) == [
            "Test Stream 1",
            "Test Stream 2",
        ]


async def test_metadata(
    hass: HomeAssistant,
) -> None:
    """Test metadata is parsed from Snapcast stream."""

    # Setup the integration
    mock_config_entry = await _setup_integration(hass)
    assert mock_config_entry

    # Fetch the coordinator
    coordinator = hass.data[SNAPCAST_DOMAIN][mock_config_entry.entry_id]

    # Load the test server data manually
    coordinator.server._on_server_update(TEST_STATE)

    # Asset metadata matches in both client and group entities
    for entity_id in [TEST_CLIENT_ENTITY_ID, TEST_GROUP_ENTITY_ID]:
        state = hass.states.get(entity_id)
        assert state

        assert state.attributes[ATTR_MEDIA_ARTIST] == "Test Artist 1"
        assert state.attributes[ATTR_MEDIA_ALBUM_ARTIST] == "Test Album Artist 1"
        assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Test Album"
        assert state.attributes[ATTR_MEDIA_TITLE] == "Test Title"
        assert state.attributes[ATTR_MEDIA_TRACK] == 1
        assert state.attributes[ATTR_MEDIA_DURATION] == 60
        assert state.attributes[ATTR_MEDIA_POSITION] == 30


async def test_no_metadata(
    hass: HomeAssistant,
) -> None:
    """Test no metadata exists when a stream has no metadata."""

    # Setup the integration
    mock_config_entry = await _setup_integration(hass)
    assert mock_config_entry

    # Fetch the coordinator
    coordinator = hass.data[SNAPCAST_DOMAIN][mock_config_entry.entry_id]

    # Load the test server data manually
    coordinator.server._on_server_update(TEST_STATE)

    # Switch to the stream without metadata
    await _call_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {"entity_id": TEST_GROUP_ENTITY_ID, "source": "Test Stream 2"},
    )

    # Manually update coordinator and entities
    coordinator._on_update()

    # Assert that no metadata attributes are present in both client and group entities
    for entity_id in [TEST_CLIENT_ENTITY_ID, TEST_GROUP_ENTITY_ID]:
        state = hass.states.get(entity_id)
        assert state

        assert ATTR_MEDIA_ARTIST not in state.attributes
        assert ATTR_MEDIA_ALBUM_ARTIST not in state.attributes
        assert ATTR_MEDIA_ALBUM_NAME not in state.attributes
        assert ATTR_MEDIA_TITLE not in state.attributes
        assert ATTR_MEDIA_TRACK not in state.attributes
        assert ATTR_MEDIA_DURATION not in state.attributes
        assert ATTR_MEDIA_POSITION not in state.attributes
