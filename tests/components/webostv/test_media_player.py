"""The tests for the LG webOS media player platform."""
import asyncio
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import Mock

from aiowebostv import WebOsTvPairError
import pytest

from homeassistant.components import automation
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.components.webostv.const import (
    ATTR_BUTTON,
    ATTR_PAYLOAD,
    ATTR_SOUND_OUTPUT,
    DOMAIN,
    LIVE_TV_APP_ID,
    SERVICE_BUTTON,
    SERVICE_COMMAND,
    SERVICE_SELECT_SOUND_OUTPUT,
    WebOsTvCommandError,
)
from homeassistant.components.webostv.media_player import (
    SUPPORT_WEBOSTV,
    SUPPORT_WEBOSTV_VOLUME,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ENTITY_MATCH_NONE,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import setup_webostv
from .const import CHANNEL_2, ENTITY_ID, TV_NAME

from tests.common import async_fire_time_changed, mock_restore_cache
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("service", "attr_data", "client_call"),
    [
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}, ("set_mute", True)),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}, ("set_mute", False)),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 1.00}, ("set_volume", 100)),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.54}, ("set_volume", 54)),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.0}, ("set_volume", 0)),
    ],
)
async def test_services_with_parameters(
    hass: HomeAssistant, client, service, attr_data, client_call
) -> None:
    """Test services that has parameters in calls."""
    await setup_webostv(hass)

    data = {ATTR_ENTITY_ID: ENTITY_ID, **attr_data}
    await hass.services.async_call(MP_DOMAIN, service, data, True)

    getattr(client, client_call[0]).assert_called_once_with(client_call[1])


@pytest.mark.parametrize(
    ("service", "client_call"),
    [
        (SERVICE_TURN_OFF, "power_off"),
        (SERVICE_VOLUME_UP, "volume_up"),
        (SERVICE_VOLUME_DOWN, "volume_down"),
        (SERVICE_MEDIA_PLAY, "play"),
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_STOP, "stop"),
    ],
)
async def test_services(hass: HomeAssistant, client, service, client_call) -> None:
    """Test simple services without parameters."""
    await setup_webostv(hass)

    data = {ATTR_ENTITY_ID: ENTITY_ID}
    await hass.services.async_call(MP_DOMAIN, service, data, True)

    getattr(client, client_call).assert_called_once()


async def test_media_play_pause(hass: HomeAssistant, client) -> None:
    """Test media play pause service."""
    await setup_webostv(hass)

    data = {ATTR_ENTITY_ID: ENTITY_ID}

    # After init state is playing - check pause call
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, data, True)

    client.pause.assert_called_once()
    client.play.assert_not_called()

    # After pause state is paused - check play call
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, data, True)

    client.play.assert_called_once()
    client.pause.assert_called_once()


@pytest.mark.parametrize(
    ("service", "client_call"),
    [
        (SERVICE_MEDIA_NEXT_TRACK, ("fast_forward", "channel_up")),
        (SERVICE_MEDIA_PREVIOUS_TRACK, ("rewind", "channel_down")),
    ],
)
async def test_media_next_previous_track(
    hass: HomeAssistant, client, service, client_call, monkeypatch
) -> None:
    """Test media next/previous track services."""
    await setup_webostv(hass)

    # check channel up/down for live TV channels
    data = {ATTR_ENTITY_ID: ENTITY_ID}
    await hass.services.async_call(MP_DOMAIN, service, data, True)

    getattr(client, client_call[0]).assert_not_called()
    getattr(client, client_call[1]).assert_called_once()

    # check next/previous for not Live TV channels
    monkeypatch.setattr(client, "current_app_id", "in1")
    data = {ATTR_ENTITY_ID: ENTITY_ID}
    await hass.services.async_call(MP_DOMAIN, service, data, True)

    getattr(client, client_call[0]).assert_called_once()
    getattr(client, client_call[1]).assert_called_once()


async def test_select_source_with_empty_source_list(
    hass: HomeAssistant, client, caplog: pytest.LogCaptureFixture
) -> None:
    """Ensure we don't call client methods when we don't have sources."""
    await setup_webostv(hass)
    await client.mock_state_update()

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_INPUT_SOURCE: "nonexistent",
    }
    await hass.services.async_call(MP_DOMAIN, SERVICE_SELECT_SOURCE, data, True)

    client.launch_app.assert_not_called()
    client.set_input.assert_not_called()
    assert f"Source nonexistent not found for {TV_NAME}" in caplog.text


async def test_select_app_source(hass: HomeAssistant, client) -> None:
    """Test select app source."""
    await setup_webostv(hass)
    await client.mock_state_update()

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_INPUT_SOURCE: "Live TV",
    }
    await hass.services.async_call(MP_DOMAIN, SERVICE_SELECT_SOURCE, data, True)

    client.launch_app.assert_called_once_with(LIVE_TV_APP_ID)
    client.set_input.assert_not_called()


async def test_select_input_source(hass: HomeAssistant, client) -> None:
    """Test select input source."""
    await setup_webostv(hass)
    await client.mock_state_update()

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_INPUT_SOURCE: "Input01",
    }
    await hass.services.async_call(MP_DOMAIN, SERVICE_SELECT_SOURCE, data, True)

    client.launch_app.assert_not_called()
    client.set_input.assert_called_once_with("in1")


async def test_button(hass: HomeAssistant, client) -> None:
    """Test generic button functionality."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_BUTTON: "test",
    }
    await hass.services.async_call(DOMAIN, SERVICE_BUTTON, data, True)
    await hass.async_block_till_done()
    client.button.assert_called_once()
    client.button.assert_called_with("test")


async def test_command(hass: HomeAssistant, client) -> None:
    """Test generic command functionality."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test",
    }
    await hass.services.async_call(DOMAIN, SERVICE_COMMAND, data, True)
    await hass.async_block_till_done()
    client.request.assert_called_with("test", payload=None)


async def test_command_with_optional_arg(hass: HomeAssistant, client) -> None:
    """Test generic command functionality."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test",
        ATTR_PAYLOAD: {"target": "https://www.google.com"},
    }
    await hass.services.async_call(DOMAIN, SERVICE_COMMAND, data, True)
    await hass.async_block_till_done()
    client.request.assert_called_with(
        "test", payload={"target": "https://www.google.com"}
    )


async def test_select_sound_output(hass: HomeAssistant, client) -> None:
    """Test select sound output service."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_SOUND_OUTPUT: "external_speaker",
    }
    await hass.services.async_call(DOMAIN, SERVICE_SELECT_SOUND_OUTPUT, data, True)
    await hass.async_block_till_done()
    client.change_sound_output.assert_called_once_with("external_speaker")


async def test_device_info_startup_off(
    hass: HomeAssistant, client, monkeypatch, device_registry: dr.DeviceRegistry
) -> None:
    """Test device info when device is off at startup."""
    monkeypatch.setattr(client, "system_info", None)
    monkeypatch.setattr(client, "is_on", False)
    entry = await setup_webostv(hass)
    await client.mock_state_update()

    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.unique_id)})

    assert device
    assert device.identifiers == {(DOMAIN, entry.unique_id)}
    assert device.manufacturer == "LG"
    assert device.name == TV_NAME
    assert device.sw_version is None
    assert device.model is None


async def test_entity_attributes(
    hass: HomeAssistant, client, monkeypatch, device_registry: dr.DeviceRegistry
) -> None:
    """Test entity attributes."""
    entry = await setup_webostv(hass)
    await client.mock_state_update()

    # Attributes when device is on
    state = hass.states.get(ENTITY_ID)
    attrs = state.attributes

    assert state.state == STATE_ON
    assert state.name == TV_NAME
    assert attrs[ATTR_DEVICE_CLASS] == MediaPlayerDeviceClass.TV
    assert attrs[ATTR_MEDIA_VOLUME_MUTED] is False
    assert attrs[ATTR_MEDIA_VOLUME_LEVEL] == 0.37
    assert attrs[ATTR_INPUT_SOURCE] == "Live TV"
    assert attrs[ATTR_INPUT_SOURCE_LIST] == ["Input01", "Input02", "Live TV"]
    assert attrs[ATTR_MEDIA_CONTENT_TYPE] == MediaType.CHANNEL
    assert attrs[ATTR_MEDIA_TITLE] == "Channel 1"
    assert attrs[ATTR_SOUND_OUTPUT] == "speaker"

    # Volume level not available
    monkeypatch.setattr(client, "volume", None)
    await client.mock_state_update()
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs.get(ATTR_MEDIA_VOLUME_LEVEL) is None

    # Channel change
    monkeypatch.setattr(client, "current_channel", CHANNEL_2)
    await client.mock_state_update()
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_MEDIA_TITLE] == "Channel Name 2"

    # Device Info
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.unique_id)})

    assert device
    assert device.identifiers == {(DOMAIN, entry.unique_id)}
    assert device.manufacturer == "LG"
    assert device.name == TV_NAME
    assert device.sw_version == "major.minor"
    assert device.model == "TVFAKE"

    # Sound output when off
    monkeypatch.setattr(client, "sound_output", None)
    monkeypatch.setattr(client, "is_on", False)
    await client.mock_state_update()
    state = hass.states.get(ENTITY_ID)

    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SOUND_OUTPUT) is None


async def test_service_entity_id_none(hass: HomeAssistant, client) -> None:
    """Test service call with none as entity id."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_MATCH_NONE,
        ATTR_SOUND_OUTPUT: "external_speaker",
    }
    await hass.services.async_call(DOMAIN, SERVICE_SELECT_SOUND_OUTPUT, data, True)

    client.change_sound_output.assert_not_called()


@pytest.mark.parametrize(
    ("media_id", "ch_id"),
    [
        ("Channel 1", "ch1id"),  # Perfect Match by channel name
        ("Name 2", "ch2id"),  # Partial Match by channel name
        ("20", "ch2id"),  # Perfect Match by channel number
    ],
)
async def test_play_media(hass: HomeAssistant, client, media_id, ch_id) -> None:
    """Test play media service."""
    await setup_webostv(hass)
    await client.mock_state_update()

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_MEDIA_CONTENT_TYPE: MediaType.CHANNEL,
        ATTR_MEDIA_CONTENT_ID: media_id,
    }
    await hass.services.async_call(MP_DOMAIN, SERVICE_PLAY_MEDIA, data, True)

    client.set_channel.assert_called_once_with(ch_id)


async def test_update_sources_live_tv_find(
    hass: HomeAssistant, client, monkeypatch
) -> None:
    """Test finding live TV app id in update sources."""
    await setup_webostv(hass)
    await client.mock_state_update()

    # Live TV found in app list
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]

    assert "Live TV" in sources
    assert len(sources) == 3

    # Live TV is current app
    apps = {
        LIVE_TV_APP_ID: {
            "title": "Live TV",
            "id": "some_id",
        },
    }
    monkeypatch.setattr(client, "apps", apps)
    monkeypatch.setattr(client, "current_app_id", "some_id")
    await client.mock_state_update()
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]

    assert "Live TV" in sources
    assert len(sources) == 3

    # Live TV is is in inputs
    inputs = {
        LIVE_TV_APP_ID: {
            "label": "Live TV",
            "id": "some_id",
            "appId": LIVE_TV_APP_ID,
        },
    }
    monkeypatch.setattr(client, "inputs", inputs)
    await client.mock_state_update()
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]

    assert "Live TV" in sources
    assert len(sources) == 1

    # Live TV is current input
    inputs = {
        LIVE_TV_APP_ID: {
            "label": "Live TV",
            "id": "some_id",
            "appId": "some_id",
        },
    }
    monkeypatch.setattr(client, "inputs", inputs)
    await client.mock_state_update()
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]

    assert "Live TV" in sources
    assert len(sources) == 1

    # Live TV not found
    monkeypatch.setattr(client, "current_app_id", "other_id")
    await client.mock_state_update()
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]

    assert "Live TV" in sources
    assert len(sources) == 1

    # Live TV not found in sources/apps but is current app
    monkeypatch.setattr(client, "apps", {})
    monkeypatch.setattr(client, "current_app_id", LIVE_TV_APP_ID)
    await client.mock_state_update()
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]

    assert "Live TV" in sources
    assert len(sources) == 1

    # Bad update, keep old update
    monkeypatch.setattr(client, "inputs", {})
    await client.mock_state_update()
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]

    assert "Live TV" in sources
    assert len(sources) == 1


async def test_client_disconnected(hass: HomeAssistant, client, monkeypatch) -> None:
    """Test error not raised when client is disconnected."""
    await setup_webostv(hass)
    monkeypatch.setattr(client, "is_connected", Mock(return_value=False))
    monkeypatch.setattr(client, "connect", Mock(side_effect=asyncio.TimeoutError))

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()


async def test_control_error_handling(
    hass: HomeAssistant, client, caplog: pytest.LogCaptureFixture, monkeypatch
) -> None:
    """Test control errors handling."""
    await setup_webostv(hass)
    monkeypatch.setattr(client, "play", Mock(side_effect=WebOsTvCommandError))
    data = {ATTR_ENTITY_ID: ENTITY_ID}

    # Device on, raise HomeAssistantError
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, data, True)

    assert (
        str(exc.value)
        == f"Error calling async_media_play on entity {ENTITY_ID}, state:on"
    )
    assert client.play.call_count == 1

    # Device off, log a warning
    monkeypatch.setattr(client, "is_on", False)
    monkeypatch.setattr(client, "play", Mock(side_effect=asyncio.TimeoutError))
    await client.mock_state_update()
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, data, True)

    assert client.play.call_count == 1
    assert (
        f"Error calling async_media_play on entity {ENTITY_ID}, state:off, error:"
        " TimeoutError()" in caplog.text
    )


async def test_supported_features(hass: HomeAssistant, client, monkeypatch) -> None:
    """Test test supported features."""
    monkeypatch.setattr(client, "sound_output", "lineout")
    await setup_webostv(hass)
    await client.mock_state_update()

    # No sound control support
    supported = SUPPORT_WEBOSTV
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported

    # Support volume mute, step
    monkeypatch.setattr(client, "sound_output", "external_speaker")
    await client.mock_state_update()
    supported = supported | SUPPORT_WEBOSTV_VOLUME
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported

    # Support volume mute, step, set
    monkeypatch.setattr(client, "sound_output", "speaker")
    await client.mock_state_update()
    supported = supported | SUPPORT_WEBOSTV_VOLUME | MediaPlayerEntityFeature.VOLUME_SET
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported

    # Support turn on
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "webostv.turn_on",
                        "entity_id": ENTITY_ID,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": ENTITY_ID,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )
    supported |= MediaPlayerEntityFeature.TURN_ON
    await client.mock_state_update()
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported


async def test_cached_supported_features(
    hass: HomeAssistant, client, monkeypatch
) -> None:
    """Test test supported features."""
    monkeypatch.setattr(client, "is_on", False)
    monkeypatch.setattr(client, "sound_output", None)
    supported = (
        SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | MediaPlayerEntityFeature.TURN_ON
    )
    mock_restore_cache(
        hass,
        [
            State(
                ENTITY_ID,
                STATE_OFF,
                attributes={
                    ATTR_SUPPORTED_FEATURES: supported,
                },
            )
        ],
    )
    await setup_webostv(hass)
    await client.mock_state_update()

    # TV off, restored state supports mute, step
    # validate MediaPlayerEntityFeature.TURN_ON is not cached
    attrs = hass.states.get(ENTITY_ID).attributes

    assert (
        attrs[ATTR_SUPPORTED_FEATURES] == supported & ~MediaPlayerEntityFeature.TURN_ON
    )

    # TV on, support volume mute, step
    monkeypatch.setattr(client, "is_on", True)
    monkeypatch.setattr(client, "sound_output", "external_speaker")
    await client.mock_state_update()

    supported = SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported

    # TV off, support volume mute, step
    monkeypatch.setattr(client, "is_on", False)
    monkeypatch.setattr(client, "sound_output", None)
    await client.mock_state_update()

    supported = SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported

    # TV on, support volume mute, step, set
    monkeypatch.setattr(client, "is_on", True)
    monkeypatch.setattr(client, "sound_output", "speaker")
    await client.mock_state_update()

    supported = (
        SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | MediaPlayerEntityFeature.VOLUME_SET
    )
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported

    # TV off, support volume mute, step, set
    monkeypatch.setattr(client, "is_on", False)
    monkeypatch.setattr(client, "sound_output", None)
    await client.mock_state_update()

    supported = (
        SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | MediaPlayerEntityFeature.VOLUME_SET
    )
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported

    # Test support turn on is updated on cached state
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "webostv.turn_on",
                        "entity_id": ENTITY_ID,
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": ENTITY_ID,
                            "id": "{{ trigger.id }}",
                        },
                    },
                },
            ],
        },
    )
    await client.mock_state_update()

    attrs = hass.states.get(ENTITY_ID).attributes

    assert (
        attrs[ATTR_SUPPORTED_FEATURES] == supported | MediaPlayerEntityFeature.TURN_ON
    )


async def test_supported_features_no_cache(
    hass: HomeAssistant, client, monkeypatch
) -> None:
    """Test supported features if device is off and no cache."""
    monkeypatch.setattr(client, "is_on", False)
    monkeypatch.setattr(client, "sound_output", None)
    await setup_webostv(hass)

    supported = (
        SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | MediaPlayerEntityFeature.VOLUME_SET
    )
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported


async def test_supported_features_ignore_cache(hass: HomeAssistant, client) -> None:
    """Test ignore cached supported features if device is on at startup."""
    mock_restore_cache(
        hass,
        [
            State(
                ENTITY_ID,
                STATE_OFF,
                attributes={
                    ATTR_SUPPORTED_FEATURES: SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME,
                },
            )
        ],
    )
    await setup_webostv(hass)

    supported = (
        SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | MediaPlayerEntityFeature.VOLUME_SET
    )
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported


async def test_get_image_http(
    hass: HomeAssistant,
    client,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch,
) -> None:
    """Test get image via http."""
    url = "http://something/valid_icon"
    monkeypatch.setitem(client.apps[LIVE_TV_APP_ID], "icon", url)
    await setup_webostv(hass)
    await client.mock_state_update()

    attrs = hass.states.get(ENTITY_ID).attributes
    assert "entity_picture_local" not in attrs

    aioclient_mock.get(url, text="image")
    client = await hass_client_no_auth()

    resp = await client.get(attrs["entity_picture"])
    content = await resp.read()

    assert content == b"image"


async def test_get_image_http_error(
    hass: HomeAssistant,
    client,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    monkeypatch,
) -> None:
    """Test get image via http error."""
    url = "http://something/icon_error"
    monkeypatch.setitem(client.apps[LIVE_TV_APP_ID], "icon", url)
    await setup_webostv(hass)
    await client.mock_state_update()

    attrs = hass.states.get(ENTITY_ID).attributes
    assert "entity_picture_local" not in attrs

    aioclient_mock.get(url, exc=asyncio.TimeoutError())
    client = await hass_client_no_auth()

    resp = await client.get(attrs["entity_picture"])
    content = await resp.read()

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert f"Error retrieving proxied image from {url}" in caplog.text
    assert content == b""


async def test_get_image_https(
    hass: HomeAssistant,
    client,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    monkeypatch,
) -> None:
    """Test get image via http."""
    url = "https://something/valid_icon_https"
    monkeypatch.setitem(client.apps[LIVE_TV_APP_ID], "icon", url)
    await setup_webostv(hass)
    await client.mock_state_update()

    attrs = hass.states.get(ENTITY_ID).attributes
    assert "entity_picture_local" not in attrs

    aioclient_mock.get(url, text="https_image")
    client = await hass_client_no_auth()

    resp = await client.get(attrs["entity_picture"])
    content = await resp.read()

    assert content == b"https_image"


async def test_reauth_reconnect(hass: HomeAssistant, client, monkeypatch) -> None:
    """Test reauth flow triggered by reconnect."""
    entry = await setup_webostv(hass)
    monkeypatch.setattr(client, "is_connected", Mock(return_value=False))
    monkeypatch.setattr(client, "connect", Mock(side_effect=WebOsTvPairError))

    assert entry.state == ConfigEntryState.LOADED

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
