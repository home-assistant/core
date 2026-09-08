"""Test Music Assistant actions."""

from unittest.mock import AsyncMock, MagicMock, call

from music_assistant_models.config_entries import ProviderConfig, ProviderError
from music_assistant_models.enums import MediaType, ProviderStatus, ProviderType
from music_assistant_models.errors import UserNotFoundError
from music_assistant_models.media_items import SearchResults
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.music_assistant.const import (
    ATTR_FAVORITE,
    ATTR_MEDIA_TYPE,
    ATTR_PROVIDER_TYPE,
    ATTR_SEARCH_NAME,
    ATTR_USERNAME,
    DOMAIN,
)
from homeassistant.components.music_assistant.services import (
    SERVICE_GET_LIBRARY,
    SERVICE_GET_PROVIDERS,
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
        require_schema=35,
    )


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
            ATTR_FAVORITE: False,
            ATTR_MEDIA_TYPE: media_type,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


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
            ATTR_FAVORITE: False,
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


async def test_get_providers_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test music assistant get_providers action."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)

    music_assistant_client.config.get_provider_configs = AsyncMock(
        return_value=[
            ProviderConfig(
                values={},
                type=ProviderType.MUSIC,
                domain="spotify",
                instance_id="spotify-1234",
                enabled=True,
                name=None,
                default_name="Spotify",
                status=ProviderStatus.LOADED,
            ),
            ProviderConfig(
                values={},
                type=ProviderType.PLAYER,
                domain="squeezelite",
                instance_id="squeezelite-5678",
                enabled=True,
                name="Living room",
                default_name="Squeezelite",
                status=ProviderStatus.LOADED,
            ),
        ]
    )
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PROVIDERS,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_get_providers_action_with_type_filter(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test get_providers action forwards the provider type filter."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    music_assistant_client.config.get_provider_configs = AsyncMock(return_value=[])

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PROVIDERS,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_PROVIDER_TYPE: "music",
        },
        blocking=True,
        return_response=True,
    )
    assert music_assistant_client.config.get_provider_configs.call_args == call(
        provider_type=ProviderType.MUSIC,
    )


async def test_get_providers_action_with_error(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get_providers action surfaces a provider load error."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)

    music_assistant_client.config.get_provider_configs = AsyncMock(
        return_value=[
            ProviderConfig(
                values={},
                type=ProviderType.MUSIC,
                domain="ytmusic",
                instance_id="ytmusic-9012",
                enabled=True,
                name=None,
                default_name="YouTube Music",
                status=ProviderStatus.AUTH_REQUIRED,
                last_error=ProviderError(
                    error_code=11,
                    message="Authentication required",
                ),
            ),
        ]
    )
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PROVIDERS,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
