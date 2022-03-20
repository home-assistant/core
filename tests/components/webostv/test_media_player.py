"""The tests for the LG webOS media player platform."""
import asyncio
from datetime import timedelta
from unittest.mock import Mock

import pytest

from homeassistant.components import automation
from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    MediaPlayerDeviceClass,
)
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    MEDIA_TYPE_CHANNEL,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
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
from homeassistant.core import State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from . import setup_webostv
from .const import CHANNEL_2, ENTITY_ID, TV_NAME

from tests.common import async_fire_time_changed, mock_restore_cache


@pytest.mark.parametrize(
    "service, attr_data, client_call",
    [
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: True}, ("set_mute", True)),
        (SERVICE_VOLUME_MUTE, {ATTR_MEDIA_VOLUME_MUTED: False}, ("set_mute", False)),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 1.00}, ("set_volume", 100)),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.54}, ("set_volume", 54)),
        (SERVICE_VOLUME_SET, {ATTR_MEDIA_VOLUME_LEVEL: 0.0}, ("set_volume", 0)),
    ],
)
async def test_services_with_parameters(hass, client, service, attr_data, client_call):
    """Test services that has parameters in calls."""
    await setup_webostv(hass)

    data = {ATTR_ENTITY_ID: ENTITY_ID, **attr_data}
    assert await hass.services.async_call(MP_DOMAIN, service, data, True)

    getattr(client, client_call[0]).assert_called_once_with(client_call[1])


@pytest.mark.parametrize(
    "service, client_call",
    [
        (SERVICE_TURN_OFF, "power_off"),
        (SERVICE_VOLUME_UP, "volume_up"),
        (SERVICE_VOLUME_DOWN, "volume_down"),
        (SERVICE_MEDIA_PLAY, "play"),
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_STOP, "stop"),
    ],
)
async def test_services(hass, client, service, client_call):
    """Test simple services without parameters."""
    await setup_webostv(hass)

    data = {ATTR_ENTITY_ID: ENTITY_ID}
    assert await hass.services.async_call(MP_DOMAIN, service, data, True)

    getattr(client, client_call).assert_called_once()


async def test_media_play_pause(hass, client):
    """Test media play pause service."""
    await setup_webostv(hass)

    data = {ATTR_ENTITY_ID: ENTITY_ID}

    # After init state is playing - check pause call
    assert await hass.services.async_call(
        MP_DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, data, True
    )

    client.pause.assert_called_once()
    client.play.assert_not_called()

    # After pause state is paused - check play call
    assert await hass.services.async_call(
        MP_DOMAIN, SERVICE_MEDIA_PLAY_PAUSE, data, True
    )

    client.play.assert_called_once()
    client.pause.assert_called_once()


@pytest.mark.parametrize(
    "service, client_call",
    [
        (SERVICE_MEDIA_NEXT_TRACK, ("fast_forward", "channel_up")),
        (SERVICE_MEDIA_PREVIOUS_TRACK, ("rewind", "channel_down")),
    ],
)
async def test_media_next_previous_track(
    hass, client, service, client_call, monkeypatch
):
    """Test media next/previous track services."""
    await setup_webostv(hass)

    # check channel up/down for live TV channels
    data = {ATTR_ENTITY_ID: ENTITY_ID}
    assert await hass.services.async_call(MP_DOMAIN, service, data, True)

    getattr(client, client_call[0]).assert_not_called()
    getattr(client, client_call[1]).assert_called_once()

    # check next/previous for not Live TV channels
    monkeypatch.setattr(client, "current_app_id", "in1")
    data = {ATTR_ENTITY_ID: ENTITY_ID}
    assert await hass.services.async_call(MP_DOMAIN, service, data, True)

    getattr(client, client_call[0]).assert_called_once()
    getattr(client, client_call[1]).assert_called_once()


async def test_select_source_with_empty_source_list(hass, client, caplog):
    """Ensure we don't call client methods when we don't have sources."""
    await setup_webostv(hass)
    await client.mock_state_update()

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_INPUT_SOURCE: "nonexistent",
    }
    assert await hass.services.async_call(MP_DOMAIN, SERVICE_SELECT_SOURCE, data, True)

    client.launch_app.assert_not_called()
    client.set_input.assert_not_called()
    assert f"Source nonexistent not found for {TV_NAME}" in caplog.text


async def test_select_app_source(hass, client):
    """Test select app source."""
    await setup_webostv(hass)
    await client.mock_state_update()

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_INPUT_SOURCE: "Live TV",
    }
    assert await hass.services.async_call(MP_DOMAIN, SERVICE_SELECT_SOURCE, data, True)

    client.launch_app.assert_called_once_with(LIVE_TV_APP_ID)
    client.set_input.assert_not_called()


async def test_select_input_source(hass, client):
    """Test select input source."""
    await setup_webostv(hass)
    await client.mock_state_update()

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_INPUT_SOURCE: "Input01",
    }
    assert await hass.services.async_call(MP_DOMAIN, SERVICE_SELECT_SOURCE, data, True)

    client.launch_app.assert_not_called()
    client.set_input.assert_called_once_with("in1")


async def test_button(hass, client):
    """Test generic button functionality."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_BUTTON: "test",
    }
    assert await hass.services.async_call(DOMAIN, SERVICE_BUTTON, data, True)

    client.button.assert_called_once()
    client.button.assert_called_with("test")


async def test_command(hass, client):
    """Test generic command functionality."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test",
    }
    assert await hass.services.async_call(DOMAIN, SERVICE_COMMAND, data, True)

    client.request.assert_called_with("test", payload=None)


async def test_command_with_optional_arg(hass, client):
    """Test generic command functionality."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test",
        ATTR_PAYLOAD: {"target": "https://www.google.com"},
    }
    assert await hass.services.async_call(DOMAIN, SERVICE_COMMAND, data, True)

    client.request.assert_called_with(
        "test", payload={"target": "https://www.google.com"}
    )


async def test_select_sound_output(hass, client):
    """Test select sound output service."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_SOUND_OUTPUT: "external_speaker",
    }
    assert await hass.services.async_call(
        DOMAIN, SERVICE_SELECT_SOUND_OUTPUT, data, True
    )

    client.change_sound_output.assert_called_once_with("external_speaker")


async def test_device_info_startup_off(hass, client, monkeypatch):
    """Test device info when device is off at startup."""
    monkeypatch.setattr(client, "system_info", None)
    monkeypatch.setattr(client, "is_on", False)
    entry = await setup_webostv(hass)
    await client.mock_state_update()

    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    device_reg = device_registry.async_get(hass)
    device = device_reg.async_get_device({(DOMAIN, entry.unique_id)})

    assert device
    assert device.identifiers == {(DOMAIN, entry.unique_id)}
    assert device.manufacturer == "LG"
    assert device.name == TV_NAME
    assert device.sw_version is None
    assert device.model is None


async def test_entity_attributes(hass, client, monkeypatch):
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
    assert attrs[ATTR_MEDIA_CONTENT_TYPE] == MEDIA_TYPE_CHANNEL
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
    device_reg = device_registry.async_get(hass)
    device = device_reg.async_get_device({(DOMAIN, entry.unique_id)})

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


async def test_service_entity_id_none(hass, client):
    """Test service call with none as entity id."""
    await setup_webostv(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_MATCH_NONE,
        ATTR_SOUND_OUTPUT: "external_speaker",
    }
    assert await hass.services.async_call(
        DOMAIN, SERVICE_SELECT_SOUND_OUTPUT, data, True
    )

    client.change_sound_output.assert_not_called()


@pytest.mark.parametrize(
    "media_id, ch_id",
    [
        ("Channel 1", "ch1id"),  # Perfect Match by channel name
        ("Name 2", "ch2id"),  # Partial Match by channel name
        ("20", "ch2id"),  # Perfect Match by channel number
    ],
)
async def test_play_media(hass, client, media_id, ch_id):
    """Test play media service."""
    await setup_webostv(hass)
    await client.mock_state_update()

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_CHANNEL,
        ATTR_MEDIA_CONTENT_ID: media_id,
    }
    assert await hass.services.async_call(MP_DOMAIN, SERVICE_PLAY_MEDIA, data, True)

    client.set_channel.assert_called_once_with(ch_id)


async def test_update_sources_live_tv_find(hass, client, monkeypatch):
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


async def test_client_disconnected(hass, client, monkeypatch):
    """Test error not raised when client is disconnected."""
    await setup_webostv(hass)
    monkeypatch.setattr(client, "is_connected", Mock(return_value=False))
    monkeypatch.setattr(client, "connect", Mock(side_effect=asyncio.TimeoutError))

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()


async def test_control_error_handling(hass, client, caplog, monkeypatch):
    """Test control errors handling."""
    await setup_webostv(hass)
    monkeypatch.setattr(client, "play", Mock(side_effect=WebOsTvCommandError))
    data = {ATTR_ENTITY_ID: ENTITY_ID}

    # Device on, raise HomeAssistantError
    with pytest.raises(HomeAssistantError) as exc:
        assert await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, data, True)

    assert (
        str(exc.value)
        == f"Error calling async_media_play on entity {ENTITY_ID}, state:on"
    )
    assert client.play.call_count == 1

    # Device off, log a warning
    monkeypatch.setattr(client, "is_on", False)
    monkeypatch.setattr(client, "play", Mock(side_effect=asyncio.TimeoutError))
    await client.mock_state_update()
    assert await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, data, True)

    assert client.play.call_count == 1
    assert (
        f"Error calling async_media_play on entity {ENTITY_ID}, state:off, error: TimeoutError()"
        in caplog.text
    )


async def test_supported_features(hass, client, monkeypatch):
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
    supported = supported | SUPPORT_WEBOSTV_VOLUME | SUPPORT_VOLUME_SET
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
    supported |= SUPPORT_TURN_ON
    await client.mock_state_update()
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported


async def test_cached_supported_features(hass, client, monkeypatch):
    """Test test supported features."""
    monkeypatch.setattr(client, "is_on", False)
    monkeypatch.setattr(client, "sound_output", None)
    supported = SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | SUPPORT_TURN_ON
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
    # validate SUPPORT_TURN_ON is not cached
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported & ~SUPPORT_TURN_ON

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

    supported = SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | SUPPORT_VOLUME_SET
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported

    # TV off, support volume mute, step, set
    monkeypatch.setattr(client, "is_on", False)
    monkeypatch.setattr(client, "sound_output", None)
    await client.mock_state_update()

    supported = SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | SUPPORT_VOLUME_SET
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

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported | SUPPORT_TURN_ON


async def test_supported_features_no_cache(hass, client, monkeypatch):
    """Test supported features if device is off and no cache."""
    monkeypatch.setattr(client, "is_on", False)
    monkeypatch.setattr(client, "sound_output", None)
    await setup_webostv(hass)

    supported = SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | SUPPORT_VOLUME_SET
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported


async def test_supported_features_ignore_cache(hass, client):
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

    supported = SUPPORT_WEBOSTV | SUPPORT_WEBOSTV_VOLUME | SUPPORT_VOLUME_SET
    attrs = hass.states.get(ENTITY_ID).attributes

    assert attrs[ATTR_SUPPORTED_FEATURES] == supported
