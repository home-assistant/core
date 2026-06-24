"""Test the Xbox media_player platform."""

from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from httpx import HTTPStatusError, RequestError, TimeoutException
import pytest
from pythonxbox.api.provider.catalog.models import CatalogResponse
from pythonxbox.api.provider.smartglass.models import (
    SmartglassConsoleStatus,
    VolumeDirection,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.components.xbox import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import (
    AsyncMock,
    Mock,
    MockConfigEntry,
    async_load_json_object_fixture,
    snapshot_platform,
)
from tests.typing import MagicMock, WebSocketGenerator


@pytest.fixture(autouse=True)
def media_player_only() -> Generator[None]:
    """Enable only the media_player platform."""
    with patch(
        "homeassistant.components.xbox.PLATFORMS",
        [Platform.MEDIA_PLAYER],
    ):
        yield


@pytest.fixture(autouse=True)
def mock_token() -> Generator[MagicMock]:
    """Mock token generator."""
    with patch("secrets.token_hex", return_value="mock_token") as token:
        yield token


@pytest.mark.parametrize(
    ("fixture_status", "fixture_catalog"),
    [
        ("smartglass_console_status.json", "catalog_product_lookup.json"),
        ("smartglass_console_status_idle.json", "catalog_product_lookup.json"),
        ("smartglass_console_status_livetv.json", "catalog_product_lookup_livetv.json"),
    ],
    ids=["app", "idle", "livetvapp"],
)
async def test_media_players(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    xbox_live_client: AsyncMock,
    fixture_status: str,
    fixture_catalog: str | None,
) -> None:
    """Test setup of the Xbox media player platform."""

    xbox_live_client.smartglass.get_console_status.return_value = (
        SmartglassConsoleStatus(
            **await async_load_json_object_fixture(hass, fixture_status, DOMAIN)  # pyright: ignore[reportArgumentType]
        )
    )
    xbox_live_client.catalog.get_product_from_alternate_id.return_value = (
        CatalogResponse(
            **await async_load_json_object_fixture(hass, fixture_catalog, DOMAIN)  # pyright: ignore[reportArgumentType]
        )
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("xbox_live_client")
async def test_browse_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test async_browse_media."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "media_player/browse_media",
            "entity_id": "media_player.xone",
        }
    )

    response = await client.receive_json()
    assert response["success"]

    assert response["result"] == snapshot(name="library")

    await client.send_json_auto_id(
        {
            "type": "media_player/browse_media",
            "entity_id": "media_player.xone",
            "media_content_id": "App",
            "media_content_type": "app",
        }
    )

    response = await client.receive_json()
    assert response["success"]

    assert response["result"] == snapshot(name="apps")

    await client.send_json_auto_id(
        {
            "type": "media_player/browse_media",
            "entity_id": "media_player.xone",
            "media_content_id": "Game",
            "media_content_type": "game",
        }
    )

    response = await client.receive_json()
    assert response["success"]

    assert response["result"] == snapshot(name="games")


@pytest.mark.parametrize(
    ("service", "service_args", "call_method", "call_args"),
    [
        (SERVICE_TURN_ON, {}, "wake_up", ()),
        (SERVICE_TURN_OFF, {}, "turn_off", ()),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}, "unmute", ()),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}, "mute", ()),
        (SERVICE_VOLUME_UP, {}, "volume", (VolumeDirection.Up,)),
        (SERVICE_VOLUME_DOWN, {}, "volume", (VolumeDirection.Down,)),
        (SERVICE_MEDIA_PLAY, {}, "play", ()),
        (SERVICE_MEDIA_PAUSE, {}, "pause", ()),
        (SERVICE_MEDIA_PREVIOUS_TRACK, {}, "previous", ()),
        (SERVICE_MEDIA_NEXT_TRACK, {}, "next", ()),
        (
            SERVICE_PLAY_MEDIA,
            {ATTR_MEDIA_CONTENT_TYPE: MediaType.APP, ATTR_MEDIA_CONTENT_ID: "Home"},
            "go_home",
            (),
        ),
        (
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: MediaType.APP,
                ATTR_MEDIA_CONTENT_ID: "327370029",
            },
            "launch_app",
            ("327370029",),
        ),
    ],
)
async def test_media_player_actions(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    config_entry: MockConfigEntry,
    service: str,
    service_args: dict[str, Any],
    call_method: str,
    call_args: set[Any],
) -> None:
    """Test media player actions."""

    xbox_live_client.smartglass.get_console_status.return_value = (
        SmartglassConsoleStatus(
            **await async_load_json_object_fixture(
                hass, "smartglass_console_status_playing.json", DOMAIN
            )  # pyright: ignore[reportArgumentType]
        )
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        target={ATTR_ENTITY_ID: "media_player.xone", **service_args},
        blocking=True,
    )

    getattr(xbox_live_client.smartglass, call_method).assert_called_once_with(
        "HIJKLMN", *call_args
    )


@pytest.mark.parametrize(
    ("service", "service_args", "call_method"),
    [
        (SERVICE_TURN_ON, {}, "wake_up"),
        (SERVICE_TURN_OFF, {}, "turn_off"),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}, "unmute"),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}, "mute"),
        (SERVICE_VOLUME_UP, {}, "volume"),
        (SERVICE_VOLUME_DOWN, {}, "volume"),
        (SERVICE_MEDIA_PLAY, {}, "play"),
        (SERVICE_MEDIA_PAUSE, {}, "pause"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, {}, "previous"),
        (SERVICE_MEDIA_NEXT_TRACK, {}, "next"),
        (
            SERVICE_PLAY_MEDIA,
            {ATTR_MEDIA_CONTENT_TYPE: MediaType.APP, ATTR_MEDIA_CONTENT_ID: "Home"},
            "go_home",
        ),
        (
            SERVICE_PLAY_MEDIA,
            {
                ATTR_MEDIA_CONTENT_TYPE: MediaType.APP,
                ATTR_MEDIA_CONTENT_ID: "327370029",
            },
            "launch_app",
        ),
    ],
)
@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        (TimeoutException(""), "timeout_exception"),
        (RequestError("", request=Mock()), "request_exception"),
        (HTTPStatusError("", request=Mock(), response=Mock()), "request_exception"),
    ],
)
async def test_media_player_action_exceptions(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    config_entry: MockConfigEntry,
    service: str,
    service_args: dict[str, Any],
    call_method: str,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test media player action exceptions."""

    xbox_live_client.smartglass.get_console_status.return_value = (
        SmartglassConsoleStatus(
            **await async_load_json_object_fixture(
                hass, "smartglass_console_status_playing.json", DOMAIN
            )  # pyright: ignore[reportArgumentType]
        )
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    getattr(xbox_live_client.smartglass, call_method).side_effect = exception

    with pytest.raises(HomeAssistantError) as e:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            target={ATTR_ENTITY_ID: "media_player.xone", **service_args},
            blocking=True,
        )
    assert e.value.translation_key == translation_key


async def test_media_player_turn_on_failed(
    hass: HomeAssistant,
    xbox_live_client: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test media player turn on failed."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    xbox_live_client.smartglass.wake_up.side_effect = (
        HTTPStatusError(
            "", request=Mock(), response=Mock(status_code=HTTPStatus.NOT_FOUND)
        ),
    )

    with pytest.raises(HomeAssistantError) as e:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_TURN_ON,
            target={ATTR_ENTITY_ID: "media_player.xone"},
            blocking=True,
        )
    assert e.value.translation_key == "turn_on_failed"
