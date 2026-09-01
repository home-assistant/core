"""Test Music Assistant actions."""

from unittest.mock import AsyncMock, MagicMock, call

from music_assistant_models.dashboard import DashboardDevice, DashboardSession
from music_assistant_models.enums import DashboardType, MediaType
from music_assistant_models.errors import UserNotFoundError
from music_assistant_models.media_items import SearchResults
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components.music_assistant.const import (
    ATTR_DASHBOARD,
    ATTR_DASHBOARD_ID,
    ATTR_FAVORITE,
    ATTR_MEDIA_TYPE,
    ATTR_PLAYER,
    ATTR_SEARCH_NAME,
    ATTR_USERNAME,
    DOMAIN,
)
from homeassistant.components.music_assistant.services import (
    SERVICE_GET_DASHBOARDS,
    SERVICE_GET_LIBRARY,
    SERVICE_HIDE_DASHBOARD,
    SERVICE_SEARCH,
    SERVICE_SHOW_DASHBOARD,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import entity_registry as er

from .common import create_library_albums_from_fixture, setup_integration_from_fixtures

from tests.common import MockConfigEntry, MockUser


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


def setup_dashboards(music_assistant_client: MagicMock) -> None:
    """Seed the mocked client with dashboard endpoints and one active session."""
    music_assistant_client.server_info.schema_version = 39
    music_assistant_client.dashboard._dashboards = {
        "chromecast_kitchen": DashboardDevice(
            dashboard_id="chromecast_kitchen",
            name="Kitchen Display",
            supported_types={DashboardType.PARTY, DashboardType.NOW_PLAYING},
            provider_domain_hint="chromecast",
        ),
        "web_client_1": DashboardDevice(
            dashboard_id="web_client_1",
            name="Web Client",
            supported_types={
                DashboardType.PARTY,
                DashboardType.NOW_PLAYING,
                DashboardType.MUSIC_QUIZ,
                DashboardType.UNKNOWN,
            },
        ),
        "unmapped_player_display": DashboardDevice(
            dashboard_id="unmapped_player_display",
            name="Unmapped Player Display",
            supported_types={DashboardType.NOW_PLAYING},
        ),
    }
    music_assistant_client.dashboard._sessions = {
        "chromecast_kitchen": DashboardSession(
            dashboard_id="chromecast_kitchen",
            name="Kitchen Display",
            dashboard=DashboardType.NOW_PLAYING,
            player_id="00:00:00:00:00:01",
        ),
        "unmapped_player_display": DashboardSession(
            dashboard_id="unmapped_player_display",
            name="Unmapped Player Display",
            dashboard=DashboardType.NOW_PLAYING,
            player_id="not-exposed-player",
        ),
    }


async def test_get_dashboards_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test music assistant get_dashboards action."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    setup_dashboards(music_assistant_client)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DASHBOARDS,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == {
        "dashboards": [
            {
                "dashboard_id": "chromecast_kitchen",
                "name": "Kitchen Display",
                "supported_dashboards": ["now_playing", "party"],
                "active_session": {
                    "dashboard": "now_playing",
                    "player": "media_player.test_player_1",
                },
            },
            {
                "dashboard_id": "web_client_1",
                "name": "Web Client",
                "supported_dashboards": ["music_quiz", "now_playing", "party"],
                "active_session": None,
            },
            {
                "dashboard_id": "unmapped_player_display",
                "name": "Unmapped Player Display",
                "supported_dashboards": ["now_playing"],
                "active_session": {
                    "dashboard": "now_playing",
                    "player": None,
                },
            },
        ]
    }


async def test_dashboard_actions_require_supported_server(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test all dashboard actions raise on a server without dashboard support."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    # the fixture server_info reports schema_version 1

    with pytest.raises(ServiceValidationError, match="does not support dashboards"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DASHBOARDS,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
            blocking=True,
            return_response=True,
        )

    with pytest.raises(ServiceValidationError, match="does not support dashboards"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
                ATTR_DASHBOARD: "party",
            },
            blocking=True,
        )

    with pytest.raises(ServiceValidationError, match="does not support dashboards"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_HIDE_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
            },
            blocking=True,
        )


async def test_show_dashboard_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test music assistant show_dashboard action."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    setup_dashboards(music_assistant_client)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SHOW_DASHBOARD,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_DASHBOARD_ID: "chromecast_kitchen",
            ATTR_DASHBOARD: "party",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_args == call(
        "dashboard/show",
        dashboard_id="chromecast_kitchen",
        dashboard=DashboardType.PARTY,
        player_id=None,
        require_schema=39,
    )


async def test_show_dashboard_action_requires_admin(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    hass_read_only_user: MockUser,
) -> None:
    """Test show_dashboard requires administrator access."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    setup_dashboards(music_assistant_client)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
                ATTR_DASHBOARD: "party",
            },
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )


async def test_show_dashboard_action_with_player(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test show_dashboard resolves the player entity to a MA player id."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    setup_dashboards(music_assistant_client)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SHOW_DASHBOARD,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_DASHBOARD_ID: "web_client_1",
            ATTR_DASHBOARD: "now_playing",
            ATTR_PLAYER: "media_player.test_player_1",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_args == call(
        "dashboard/show",
        dashboard_id="web_client_1",
        dashboard=DashboardType.NOW_PLAYING,
        player_id="00:00:00:00:00:01",
        require_schema=39,
    )


async def test_show_dashboard_action_invalid_input(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test show_dashboard input validation errors."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    setup_dashboards(music_assistant_client)

    # unknown dashboard endpoint
    with pytest.raises(ServiceValidationError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "does_not_exist",
                ATTR_DASHBOARD: "party",
            },
            blocking=True,
        )

    # now_playing requires a player
    with pytest.raises(ServiceValidationError, match="player is required"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
                ATTR_DASHBOARD: "now_playing",
            },
            blocking=True,
        )

    # player entity must be a Music Assistant player
    with pytest.raises(ServiceValidationError, match="not a Music Assistant player"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
                ATTR_DASHBOARD: "now_playing",
                ATTR_PLAYER: "media_player.some_other_player",
            },
            blocking=True,
        )

    # player entity belongs to a different config entry
    other_entry = MockConfigEntry(domain=DOMAIN, unique_id="other_server")
    other_entry.add_to_hass(hass)
    other_entry_player = entity_registry.async_get_or_create(
        "media_player", DOMAIN, "other-player-id", config_entry=other_entry
    )
    with pytest.raises(ServiceValidationError, match="not a Music Assistant player"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
                ATTR_DASHBOARD: "now_playing",
                ATTR_PLAYER: other_entry_player.entity_id,
            },
            blocking=True,
        )

    # player entity belongs to a different integration
    demo_player = entity_registry.async_get_or_create(
        "media_player", "demo", "demo-player-1"
    )
    with pytest.raises(ServiceValidationError, match="not a Music Assistant player"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
                ATTR_DASHBOARD: "now_playing",
                ATTR_PLAYER: demo_player.entity_id,
            },
            blocking=True,
        )


async def test_show_dashboard_action_invalid_dashboard_type(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test show_dashboard rejects an unknown dashboard type with a readable error."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    setup_dashboards(music_assistant_client)

    with pytest.raises(ServiceValidationError, match="Unsupported dashboard"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
                ATTR_DASHBOARD: "definitely_not_a_dashboard",
            },
            blocking=True,
        )


async def test_show_dashboard_action_invalid_player_domain(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test show_dashboard rejects a non-media_player entity at the schema level."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    setup_dashboards(music_assistant_client)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
                ATTR_DASHBOARD: "now_playing",
                ATTR_PLAYER: "switch.test_player_1",
            },
            blocking=True,
        )


async def test_show_dashboard_action_unsupported_dashboard(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test show_dashboard rejects a dashboard the endpoint does not support."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    setup_dashboards(music_assistant_client)

    with pytest.raises(ServiceValidationError, match="does not support"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SHOW_DASHBOARD,
            {
                ATTR_CONFIG_ENTRY_ID: entry.entry_id,
                ATTR_DASHBOARD_ID: "chromecast_kitchen",
                ATTR_DASHBOARD: "music_quiz",
            },
            blocking=True,
        )


async def test_hide_dashboard_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test music assistant hide_dashboard action."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    setup_dashboards(music_assistant_client)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_HIDE_DASHBOARD,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_DASHBOARD_ID: "chromecast_kitchen",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_args == call(
        "dashboard/hide",
        dashboard_id="chromecast_kitchen",
        require_schema=39,
    )

    # hiding an unknown dashboard endpoint is a no-op forwarded to the server
    await hass.services.async_call(
        DOMAIN,
        SERVICE_HIDE_DASHBOARD,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_DASHBOARD_ID: "does_not_exist",
        },
        blocking=True,
    )
    assert music_assistant_client.send_command.call_args == call(
        "dashboard/hide",
        dashboard_id="does_not_exist",
        require_schema=39,
    )
