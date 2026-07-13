"""Test Music Assistant actions."""

from unittest.mock import AsyncMock, MagicMock, call

from music_assistant_models.enums import MediaType
from music_assistant_models.media_items import SearchResults
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.music_assistant.const import (
    ATTR_FAVORITE,
    ATTR_MEDIA_TYPE,
    ATTR_SEARCH_NAME,
    ATTR_USERNAME,
    DOMAIN,
)
from homeassistant.components.music_assistant.services import (
    SERVICE_GET_LIBRARY,
    SERVICE_SEARCH,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .common import create_library_albums_from_fixture, setup_integration_from_fixtures


async def test_search_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test music assistant search action."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)

    music_assistant_client.music.search = AsyncMock(
        return_value=SearchResults(
            albums=create_library_albums_from_fixture(),
        )
    )
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_SEARCH_NAME: "test",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_search_action_with_username(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test music assistant search action."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)

    # services with an api version < 35 must raise a validation error even if the username is valid
    music_assistant_client.server_info.schema_version = 30
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_SEARCH_NAME: "test",
                ATTR_USERNAME: "user_user",
            },
            blocking=True,
            return_response=True,
        )
    assert exc.value.translation_key == "unsupported_parameter"

    # tests for servers supporting the username
    music_assistant_client.server_info.schema_version = 35
    # mock client's send_command for username tests
    music_assistant_client.music.client.send_command = AsyncMock(
        return_value={"albums": []}
    )

    # valid user ok and forwarded
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_SEARCH_NAME: "test",
            ATTR_USERNAME: "user_user",
        },
        blocking=True,
        return_response=True,
    )
    assert music_assistant_client.send_command.call_count == 1
    assert music_assistant_client.send_command.call_args == call(
        "music/search",
        search_query="test",
        media_types=MediaType.ALL,
        limit=5,
        library_only=False,
        user="user_user",
        require_schema=35,
    )

    # not valid because of name, disabled or guest
    for username in ("non_existing_user", "party_guest", "user_disabled"):
        with pytest.raises(ServiceValidationError) as exc:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SEARCH,
                {
                    ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                    ATTR_SEARCH_NAME: "test",
                    ATTR_USERNAME: username,
                },
                blocking=True,
                return_response=True,
            )
        assert exc.value.translation_key == "invalid_username"


@pytest.mark.parametrize(
    "media_type",
    [
        "artist",
        "album",
        "track",
        "playlist",
        "audiobook",
        "podcast",
        "radio",
    ],
)
async def test_get_library_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_type: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test music assistant get_library action."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_LIBRARY,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_FAVORITE: False,
            ATTR_MEDIA_TYPE: media_type,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
