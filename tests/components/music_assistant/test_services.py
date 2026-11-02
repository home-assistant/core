"""Test Music Assistant actions."""

from unittest.mock import AsyncMock, MagicMock, call

from music_assistant_client.helpers import LinkedUser
from music_assistant_models.auth import AuthProviderType
from music_assistant_models.enums import MediaType
from music_assistant_models.errors import UserNotFoundError
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
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .common import create_library_albums_from_fixture, setup_integration_from_fixtures

MOCK_USER_ID = "abc123"


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

    # tests for servers supporting the username
    music_assistant_client.server_info.schema_version = 35
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
    )


@pytest.mark.parametrize(
    ("user_id", "extra_data", "expected_user"),
    [
        pytest.param(
            MOCK_USER_ID,
            {},
            LinkedUser(
                provider=AuthProviderType.HOME_ASSISTANT,
                user_id=MOCK_USER_ID,
                required=False,
            ),
            id="calling user",
        ),
        pytest.param(None, {}, None, id="no calling user"),
        pytest.param(
            MOCK_USER_ID,
            {ATTR_USERNAME: "user_user"},
            "user_user",
            id="explicit username wins",
        ),
    ],
)
async def test_search_action_acts_as_calling_user(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    user_id: str | None,
    extra_data: dict[str, str],
    expected_user: LinkedUser | str | None,
) -> None:
    """Test that the search action defaults to the user that called it."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    music_assistant_client.music.search = AsyncMock(return_value=SearchResults())

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_SEARCH_NAME: "test",
            **extra_data,
        },
        blocking=True,
        return_response=True,
        context=Context(user_id=user_id),
    )

    assert music_assistant_client.music.search.call_args.kwargs["user"] == expected_user


async def test_search_action_with_unknown_username(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that a username the server does not know raises a translated error."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    music_assistant_client.music.search = AsyncMock(
        side_effect=UserNotFoundError(
            "A user with user id or name nobody is not available."
        )
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_SEARCH_NAME: "test",
                ATTR_USERNAME: "nobody",
            },
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == "invalid_username"
    assert err.value.translation_placeholders == {"username": "nobody"}


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
            ATTR_MEDIA_TYPE: media_type,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("favorite", "expected"),
    [(True, True), (False, False), (None, None)],
)
async def test_get_library_action_favorite_filter(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    favorite: bool | None,
    expected: bool | None,
) -> None:
    """Test the favorite filter is forwarded as given: a like, a dislike or absent."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    data = {ATTR_CONFIG_ENTRY_ID: entry.entry_id, ATTR_MEDIA_TYPE: "album"}
    if favorite is not None:
        data[ATTR_FAVORITE] = favorite

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_LIBRARY,
        data,
        blocking=True,
        return_response=True,
    )

    assert (
        music_assistant_client.music.get_library_albums.call_args.kwargs["favorite"]
        is expected
    )


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
async def test_get_library_action_with_username(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_type: str,
) -> None:
    """Test music assistant get_library action with username."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    # username supported from schema 35 and above
    music_assistant_client.server_info.schema_version = 35

    # an explicit username is forwarded to the server (which validates it)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_LIBRARY,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_MEDIA_TYPE: media_type,
            ATTR_USERNAME: "user_user",
        },
        blocking=True,
        return_response=True,
    )


async def test_get_library_action_with_unknown_username(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that a username the server does not know raises a translated error."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    music_assistant_client.music.get_library_tracks = AsyncMock(
        side_effect=UserNotFoundError(
            "A user with user id or name nobody is not available."
        )
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_LIBRARY,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_MEDIA_TYPE: "track",
                ATTR_USERNAME: "nobody",
            },
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == "invalid_username"
    assert err.value.translation_placeholders == {"username": "nobody"}
