"""Test the Bravia TV media player."""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import quote

from pybravia import (
    BraviaConnectionError,
    BraviaConnectionTimeout,
    BraviaError,
    BraviaNotFound,
    BraviaTurnedOff,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .conftest import BRAVIA_CHANNELS, BRAVIA_PLAYING_INFO, BRAVIA_VOLUME_INFO

ENTITY_ID = "media_player.bravia_tv_model"

CHANNEL_PLAYING_INFO = {
    "uri": "tv:dvbt?trip=1.2.3&srvName=TVP1",
    "source": "tv:dvbt",
    "title": "TVP 1",
    "dispNum": "001",
    "programTitle": "News",
    "durationSec": 3600,
    "startDateTime": "2026-08-22T11:30:00+00:00",
}

SOURCE_LIST = ["HDMI 1", "HDMI 2", "AV/Component"]

# The TV leaves "label" empty when unset, omits it on some models, and allows a
# label that only differs from the generic name in case.
LABELLED_INPUTS = [
    {"uri": "extInput:hdmi?port=1", "title": "HDMI 1"},
    {"uri": "extInput:hdmi?port=2", "title": "HDMI 2", "label": "Game console"},
    {"uri": "extInput:hdmi?port=3", "title": "HDMI 3", "label": ""},
    {"uri": "extInput:hdmi?port=4", "title": "HDMI 4", "label": "hdmi 4"},
]

BASE_ATTRIBUTES = {
    ATTR_ASSUMED_STATE: True,
    ATTR_DEVICE_CLASS: MediaPlayerDeviceClass.TV,
    ATTR_FRIENDLY_NAME: "BRAVIA TV-Model",
    ATTR_SUPPORTED_FEATURES: (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    ),
}

VOLUME_ATTRIBUTES = {ATTR_MEDIA_VOLUME_LEVEL: 0.25, ATTR_MEDIA_VOLUME_MUTED: False}

HDMI_ATTRIBUTES = {
    ATTR_INPUT_SOURCE: "HDMI 1",
    ATTR_INPUT_SOURCE_LIST: SOURCE_LIST,
    ATTR_MEDIA_CONTENT_ID: "extInput:hdmi?port=1",
    ATTR_MEDIA_TITLE: "HDMI 1",
}

CHANNEL_ATTRIBUTES = {
    ATTR_INPUT_SOURCE_LIST: SOURCE_LIST,
    ATTR_MEDIA_CHANNEL: "TVP 1",
    ATTR_MEDIA_CONTENT_ID: "001",
    ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
    ATTR_MEDIA_DURATION: 3600,
    ATTR_MEDIA_POSITION: 1800,
    ATTR_MEDIA_POSITION_UPDATED_AT: datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
    ATTR_MEDIA_TITLE: "News",
}


@pytest.mark.usefixtures("mock_braviatv_client")
async def test_media_player(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the media player entity."""
    with patch("homeassistant.components.braviatv.PLATFORMS", [Platform.MEDIA_PLAYER]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2026-08-22T12:00:00+00:00")
@pytest.mark.parametrize(
    (
        "power_status",
        "volume_info",
        "playing_info",
        "expected_state",
        "expected_attributes",
    ),
    [
        (
            "active",
            {"volume": 25, "mute": True, "target": "speaker"},
            {"uri": "extInput:hdmi?port=1", "title": "HDMI 1"},
            STATE_ON,
            {**HDMI_ATTRIBUTES, **VOLUME_ATTRIBUTES, ATTR_MEDIA_VOLUME_MUTED: True},
        ),
        (
            "active",
            BRAVIA_VOLUME_INFO,
            CHANNEL_PLAYING_INFO,
            STATE_ON,
            {**CHANNEL_ATTRIBUTES, **VOLUME_ATTRIBUTES},
        ),
        (
            "active",
            BRAVIA_VOLUME_INFO,
            {**CHANNEL_PLAYING_INFO, "startDateTime": "2026-08-22T13:30:00"},
            STATE_ON,
            {**CHANNEL_ATTRIBUTES, **VOLUME_ATTRIBUTES},
        ),
        (
            "active",
            BRAVIA_VOLUME_INFO,
            {"uri": "tv:dvbt?trip=1.2.3&srvName=TVP1", "dispNum": "001"},
            STATE_ON,
            {
                ATTR_INPUT_SOURCE_LIST: SOURCE_LIST,
                ATTR_MEDIA_CHANNEL: "001",
                ATTR_MEDIA_CONTENT_ID: "001",
                ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
                ATTR_MEDIA_TITLE: "001",
                **VOLUME_ATTRIBUTES,
            },
        ),
        (
            "active",
            BRAVIA_VOLUME_INFO,
            {"uri": "com.sony.dtv.com.netflix.ninja", "title": "Netflix"},
            STATE_ON,
            {
                ATTR_INPUT_SOURCE_LIST: SOURCE_LIST,
                ATTR_MEDIA_CONTENT_ID: "com.sony.dtv.com.netflix.ninja",
                ATTR_MEDIA_TITLE: "Netflix",
                **VOLUME_ATTRIBUTES,
            },
        ),
        (
            "active",
            BRAVIA_VOLUME_INFO,
            {},
            STATE_ON,
            {
                ATTR_INPUT_SOURCE_LIST: SOURCE_LIST,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.APP,
                ATTR_MEDIA_TITLE: "Smart TV",
                **VOLUME_ATTRIBUTES,
            },
        ),
        (
            "active",
            {"mute": True, "target": "speaker"},
            BRAVIA_PLAYING_INFO,
            STATE_ON,
            {**HDMI_ATTRIBUTES, ATTR_MEDIA_VOLUME_MUTED: False},
        ),
        ("standby", BRAVIA_VOLUME_INFO, BRAVIA_PLAYING_INFO, STATE_OFF, {}),
    ],
)
async def test_media_player_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    power_status: str,
    volume_info: dict[str, Any],
    playing_info: dict[str, Any],
    expected_state: str,
    expected_attributes: dict[str, Any],
) -> None:
    """Test the media player state follows the TV status."""
    # A naive startDateTime is local time (Europe/Warsaw is UTC+2 in August)
    await hass.config.async_set_time_zone("Europe/Warsaw")
    mock_braviatv_client.get_power_status.return_value = power_status
    mock_braviatv_client.get_volume_info.return_value = volume_info
    mock_braviatv_client.get_playing_info.return_value = playing_info
    await init_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_state
    assert state.attributes == {**BASE_ATTRIBUTES, **expected_attributes}


@pytest.mark.parametrize(
    ("service", "service_data", "method", "call_args"),
    [
        (SERVICE_TURN_ON, {}, "turn_on", ()),
        (SERVICE_TURN_OFF, {}, "turn_off", ()),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.5}, "volume_level", (50,)),
        (SERVICE_VOLUME_UP, {}, "volume_up", ()),
        (SERVICE_VOLUME_DOWN, {}, "volume_down", ()),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}, "volume_mute", ()),
        (SERVICE_MEDIA_PLAY, {}, "play", ()),
        (SERVICE_MEDIA_PAUSE, {}, "pause", ()),
        (SERVICE_MEDIA_PLAY_PAUSE, {}, "pause", ()),
        (SERVICE_MEDIA_STOP, {}, "stop", ()),
        (
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "HDMI 2"},
            "set_play_content",
            ("extInput:hdmi?port=2",),
        ),
        (
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "hdmi 1"},
            "set_play_content",
            ("extInput:hdmi?port=1",),
        ),
        (
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "hdmi"},
            "set_play_content",
            ("extInput:hdmi?port=2",),
        ),
        (
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "extInput:hdmi?port=2"},
            "set_play_content",
            ("extInput:hdmi?port=2",),
        ),
    ],
)
async def test_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    service: str,
    service_data: dict[str, Any],
    method: str,
    call_args: tuple[Any, ...],
) -> None:
    """Test media player services."""
    await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    getattr(mock_braviatv_client, method).assert_called_once_with(*call_args)


@pytest.mark.parametrize(
    ("playing_info", "service", "method"),
    [
        (CHANNEL_PLAYING_INFO, SERVICE_MEDIA_NEXT_TRACK, "channel_up"),
        (CHANNEL_PLAYING_INFO, SERVICE_MEDIA_PREVIOUS_TRACK, "channel_down"),
        (
            {"uri": "extInput:hdmi?port=1", "title": "HDMI 1"},
            SERVICE_MEDIA_NEXT_TRACK,
            "next_track",
        ),
        (
            {"uri": "extInput:hdmi?port=1", "title": "HDMI 1"},
            SERVICE_MEDIA_PREVIOUS_TRACK,
            "previous_track",
        ),
    ],
)
async def test_next_previous_track(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    playing_info: dict[str, Any],
    service: str,
    method: str,
) -> None:
    """Test next and previous track switch channels when watching TV."""
    mock_braviatv_client.get_playing_info.return_value = playing_info
    await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    getattr(mock_braviatv_client, method).assert_called_once()


async def test_select_source_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test selecting an unknown source."""
    await init_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI 9"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "source_not_found"
    assert exc_info.value.translation_placeholders == {
        "device": "BRAVIA TV-Model",
        "source_type": "input",
        "query": "HDMI 9",
    }
    mock_braviatv_client.set_play_content.assert_not_called()


async def test_source_list_skips_incomplete_items(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test sources without a title or URI are not listed."""
    mock_braviatv_client.get_external_status.return_value = [
        {"uri": "extInput:hdmi?port=1", "title": "HDMI 1"},
        {"uri": "extInput:hdmi?port=2", "title": ""},
        {"title": "AV/Component"},
    ]
    mock_braviatv_client.get_app_list.return_value = []
    mock_braviatv_client.get_content_list_all.return_value = []

    await init_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["HDMI 1"]


async def test_source_list_adds_label(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test the name set on the TV is listed next to the generic one."""
    mock_braviatv_client.get_external_status.return_value = LABELLED_INPUTS
    mock_braviatv_client.get_app_list.return_value = []
    mock_braviatv_client.get_content_list_all.return_value = []
    mock_braviatv_client.get_playing_info.return_value = {
        "uri": "extInput:hdmi?port=2",
        "title": "HDMI 2",
        "source": "extInput:hdmi",
    }

    await init_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == [
        "HDMI 1",
        "HDMI 2",
        "Game console",
        "HDMI 3",
        "HDMI 4",
    ]
    assert state.attributes[ATTR_INPUT_SOURCE] == "HDMI 2"


@pytest.mark.parametrize(
    ("source", "expected_uri"),
    [
        ("Game console", "extInput:hdmi?port=2"),
        ("HDMI 2", "extInput:hdmi?port=2"),
        ("HDMI 4", "extInput:hdmi?port=4"),
        ("hdmi 4", "extInput:hdmi?port=4"),
    ],
)
async def test_select_source_by_label(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    source: str,
    expected_uri: str,
) -> None:
    """Test selecting an input by the name set on the TV or by its generic name."""
    mock_braviatv_client.get_external_status.return_value = LABELLED_INPUTS
    await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: source},
        blocking=True,
    )

    mock_braviatv_client.set_play_content.assert_called_once_with(expected_uri)


@pytest.mark.parametrize(
    ("media_type", "media_id", "method", "uri"),
    [
        (
            MediaType.APP,
            "YouTube",
            "set_active_app",
            "com.sony.dtv.com.google.android.youtube.tv",
        ),
        (MediaType.APP, "net", "set_active_app", "com.sony.dtv.com.netflix.ninja"),
        (
            MediaType.APP,
            "com.sony.dtv.com.netflix.ninja",
            "set_active_app",
            "com.sony.dtv.com.netflix.ninja",
        ),
        (MediaType.CHANNEL, "2", "set_play_content", "tv:dvbt?trip=1.2.4&srvName=TVP2"),
        (
            MediaType.CHANNEL,
            "tv:dvbt?trip=1.2.4&srvName=TVP2",
            "set_play_content",
            "tv:dvbt?trip=1.2.4&srvName=TVP2",
        ),
        (
            MediaType.CHANNEL,
            "TVN",
            "set_play_content",
            "tv:dvbt?trip=1.2.5&srvName=TVN",
        ),
    ],
)
async def test_play_media(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    media_type: MediaType,
    media_id: str,
    method: str,
    uri: str,
) -> None:
    """Test playing apps and channels."""
    # Numeric channel search skips channels without a number
    mock_braviatv_client.get_content_list_all.return_value = [
        {"uri": "tv:dvbt?srvName=NoNum", "title": "No number"},
        *BRAVIA_CHANNELS,
    ]
    await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id,
        },
        blocking=True,
    )

    getattr(mock_braviatv_client, method).assert_called_once_with(uri)


async def test_play_media_invalid_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
) -> None:
    """Test playing an unsupported media type."""
    await init_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "song",
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_media_type"
    assert exc_info.value.translation_placeholders == {
        "device": "BRAVIA TV-Model",
        "media_type": "music",
    }
    mock_braviatv_client.set_play_content.assert_not_called()
    mock_braviatv_client.set_active_app.assert_not_called()


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (BraviaNotFound, "the Bravia API service is reloading"),
        (BraviaConnectionError, "the TV is turned off"),
        (BraviaConnectionTimeout, "the TV is turned off"),
        (BraviaTurnedOff, "the TV is turned off"),
        (BraviaError, "Error sending command to BRAVIA TV-Model: BraviaError"),
    ],
)
async def test_command_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    exception: type[Exception],
    message: str,
) -> None:
    """Test errors while sending commands."""
    await init_integration(hass, mock_config_entry)

    mock_braviatv_client.turn_on.side_effect = exception

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )


@pytest.mark.parametrize(
    ("browse_data", "app_list_calls"),
    [
        ({}, 2),
        (
            {"media_content_type": "apps", "media_content_id": "apps"},
            1,
        ),
        (
            {"media_content_type": "channels", "media_content_id": "channels"},
            1,
        ),
    ],
)
async def test_browse_media(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_braviatv_client: AsyncMock,
    browse_data: dict[str, str],
    app_list_calls: int,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing apps and channels."""
    client = await hass_ws_client(hass)

    # The thumbnail URLs contain the entity access token
    with patch("secrets.token_hex", return_value="mock_token"):
        await init_integration(hass, mock_config_entry)
        await client.send_json_auto_id(
            {"type": "media_player/browse_media", "entity_id": ENTITY_ID, **browse_data}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == snapshot
    # Browsing the root refreshes the sources fetched during setup
    assert mock_braviatv_client.get_app_list.call_count == app_list_calls


@pytest.mark.usefixtures("mock_braviatv_client")
async def test_browse_media_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing unknown media."""
    await init_integration(hass, mock_config_entry)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "media_player/browse_media",
            "entity_id": ENTITY_ID,
            "media_content_type": "foo",
            "media_content_id": "foo/bar",
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert (
        response["error"]["message"]
        == "Media foo / foo/bar was not found on BRAVIA TV-Model"
    )


@pytest.mark.parametrize(
    (
        "media_content_type",
        "media_content_id",
        "icon_headers",
        "expected_status",
        "expected_content_type",
        "expected_body",
    ),
    [
        (
            "app",
            "com.sony.dtv.com.google.android.youtube.tv",
            {"Content-Type": "Content-Type: image/png"},
            HTTPStatus.OK,
            "image/png",
            b"image",
        ),
        (
            "app",
            "com.sony.dtv.com.google.android.youtube.tv",
            {},
            HTTPStatus.OK,
            "application/octet-stream",
            b"image",
        ),
        (
            "app",
            "com.sony.dtv.com.android.tv.settings",
            {},
            HTTPStatus.NOT_FOUND,
            "application/octet-stream",
            b"",
        ),
        (
            "channel",
            "tv:dvbt?trip=1.2.3&srvName=TVP1",
            {},
            HTTPStatus.NOT_FOUND,
            "application/octet-stream",
            b"",
        ),
    ],
)
@pytest.mark.usefixtures("mock_braviatv_client")
async def test_get_browse_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    media_content_type: str,
    media_content_id: str,
    icon_headers: dict[str, str],
    expected_status: HTTPStatus,
    expected_content_type: str,
    expected_body: bytes,
) -> None:
    """Test serving app icons through the media player image proxy."""
    # Bravia returns a Content-Type header that already contains "Content-Type: "
    aioclient_mock.get(
        "http://bravia-host/youtube.png", content=b"image", headers=icon_headers
    )
    await init_integration(hass, mock_config_entry)
    client = await hass_client()

    response = await client.get(
        f"/api/media_player_proxy/{ENTITY_ID}/browse_media"
        f"/{media_content_type}/{quote(media_content_id)}"
    )

    assert response.status == expected_status
    assert response.content_type == expected_content_type
    assert await response.read() == expected_body
