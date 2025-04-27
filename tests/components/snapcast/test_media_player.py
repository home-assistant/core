"""Test the snapcast media player implementation."""

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
from homeassistant.components.snapcast.const import DOMAIN
from homeassistant.const import STATE_PLAYING
from homeassistant.core import HomeAssistant

from .const import TEST_CLIENT_ENTITY_ID, TEST_GROUP_ENTITY_ID


async def test_state(hass: HomeAssistant, mock_config_entry, mock_server_state) -> None:
    """Test basic state information."""

    # Fetch the coordinator
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # Load the test server data manually
    coordinator.server._on_server_update(mock_server_state)

    # Asset basic state matches in both client and group entities
    for entity_id in (TEST_CLIENT_ENTITY_ID, TEST_GROUP_ENTITY_ID):
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
    hass: HomeAssistant, mock_config_entry, mock_server_state
) -> None:
    """Test metadata is parsed from Snapcast stream."""

    # Fetch the coordinator
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # Load the test server data manually
    coordinator.server._on_server_update(mock_server_state)

    # Asset metadata matches in both client and group entities
    for entity_id in (TEST_CLIENT_ENTITY_ID, TEST_GROUP_ENTITY_ID):
        state = hass.states.get(entity_id)
        assert state

        assert state.attributes[ATTR_MEDIA_ARTIST] == "Test Artist 1, Test Artist 2"
        assert (
            state.attributes[ATTR_MEDIA_ALBUM_ARTIST]
            == "Test Album Artist 1, Test Album Artist 2"
        )
        assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Test Album"
        assert state.attributes[ATTR_MEDIA_TITLE] == "Test Title"
        assert state.attributes[ATTR_MEDIA_TRACK] == 10
        assert state.attributes[ATTR_MEDIA_DURATION] == 60
        assert state.attributes[ATTR_MEDIA_POSITION] == 30


async def test_no_metadata(
    hass: HomeAssistant, mock_config_entry, mock_server_state
) -> None:
    """Test no metadata exists when a stream has no metadata."""

    # Fetch the coordinator
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]

    # Load the test server data manually
    coordinator.server._on_server_update(mock_server_state)

    # Switch to the stream without metadata
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        service_data={"entity_id": TEST_GROUP_ENTITY_ID, "source": "Test Stream 2"},
        blocking=True,
    )

    # Manually update coordinator and entities
    coordinator._on_update()

    # Assert that no metadata attributes are present in both client and group entities
    for entity_id in (TEST_CLIENT_ENTITY_ID, TEST_GROUP_ENTITY_ID):
        state = hass.states.get(entity_id)
        assert state

        assert ATTR_MEDIA_ARTIST not in state.attributes
        assert ATTR_MEDIA_ALBUM_ARTIST not in state.attributes
        assert ATTR_MEDIA_ALBUM_NAME not in state.attributes
        assert ATTR_MEDIA_TITLE not in state.attributes
        assert ATTR_MEDIA_TRACK not in state.attributes
        assert ATTR_MEDIA_DURATION not in state.attributes
        assert ATTR_MEDIA_POSITION not in state.attributes
