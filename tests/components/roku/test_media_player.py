"""Tests for the Roku Media Player platform."""
from datetime import timedelta

from rokuecp import RokuError

from homeassistant.components.media_player.const import (
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_CHANNEL,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
    STATE_HOME,
    STATE_IDLE,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from tests.async_mock import patch
from tests.common import async_fire_time_changed
from tests.components.roku import UPNP_SERIAL, setup_integration
from tests.test_util.aiohttp import AiohttpClientMocker

MAIN_ENTITY_ID = f"{MP_DOMAIN}.my_roku_3"
TV_ENTITY_ID = f"{MP_DOMAIN}.58_onn_roku_tv"

TV_HOST = "192.168.1.161"
TV_SERIAL = "YN00H5555555"


async def test_setup(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with basic config."""
    await setup_integration(hass, aioclient_mock)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    main = entity_registry.async_get(MAIN_ENTITY_ID)

    assert hass.states.get(MAIN_ENTITY_ID)
    assert main
    assert main.unique_id == UPNP_SERIAL


async def test_idle_setup(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with idle device."""
    await setup_integration(hass, aioclient_mock, power=False)

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_STANDBY


async def test_tv_setup(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test Roku TV setup."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    tv = entity_registry.async_get(TV_ENTITY_ID)

    assert hass.states.get(TV_ENTITY_ID)
    assert tv
    assert tv.unique_id == TV_SERIAL


async def test_availability(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test entity availability."""
    now = dt_util.utcnow()
    future = now + timedelta(minutes=1)

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass, aioclient_mock)

    with patch(
        "homeassistant.components.roku.Roku.update", side_effect=RokuError
    ), patch("homeassistant.util.dt.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(MAIN_ENTITY_ID).state == STATE_UNAVAILABLE

    future += timedelta(minutes=1)

    with patch("homeassistant.util.dt.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(MAIN_ENTITY_ID).state == STATE_HOME


async def test_supported_features(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test supported features."""
    await setup_integration(hass, aioclient_mock)

    # Features supported for Rokus
    state = hass.states.get(MAIN_ENTITY_ID)
    assert (
        SUPPORT_PREVIOUS_TRACK
        | SUPPORT_NEXT_TRACK
        | SUPPORT_VOLUME_STEP
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_SELECT_SOURCE
        | SUPPORT_PLAY
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        == state.attributes.get("supported_features")
    )


async def test_tv_supported_features(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test supported features for Roku TV."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    state = hass.states.get(TV_ENTITY_ID)
    assert (
        SUPPORT_PREVIOUS_TRACK
        | SUPPORT_NEXT_TRACK
        | SUPPORT_VOLUME_STEP
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_SELECT_SOURCE
        | SUPPORT_PLAY
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        == state.attributes.get("supported_features")
    )


async def test_attributes(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes."""
    await setup_integration(hass, aioclient_mock)

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_HOME

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) is None
    assert state.attributes.get(ATTR_APP_ID) is None
    assert state.attributes.get(ATTR_APP_NAME) == "Roku"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Roku"


async def test_attributes_app(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes for app."""
    await setup_integration(hass, aioclient_mock, app="netflix")

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_PLAYING

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MEDIA_TYPE_APP
    assert state.attributes.get(ATTR_APP_ID) == "12"
    assert state.attributes.get(ATTR_APP_NAME) == "Netflix"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Netflix"


async def test_attributes_screensaver(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes for app with screensaver."""
    await setup_integration(hass, aioclient_mock, app="screensaver")

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_IDLE

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) is None
    assert state.attributes.get(ATTR_APP_ID) is None
    assert state.attributes.get(ATTR_APP_NAME) == "Roku"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Roku"


async def test_tv_attributes(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test attributes for Roku TV."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    state = hass.states.get(TV_ENTITY_ID)
    assert state.state == STATE_PLAYING

    assert state.attributes.get(ATTR_APP_ID) == "tvinput.dtv"
    assert state.attributes.get(ATTR_APP_NAME) == "Antenna TV"
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Antenna TV"
    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MEDIA_TYPE_CHANNEL
    assert state.attributes.get(ATTR_MEDIA_CHANNEL) == "getTV (14.3)"
    assert state.attributes.get(ATTR_MEDIA_TITLE) == "Airwolf"


async def test_services(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the different media player services."""
    await setup_integration(hass, aioclient_mock)

    with patch("homeassistant.components.roku.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: MAIN_ENTITY_ID}, blocking=True
        )

        remote_mock.assert_called_once_with("poweroff")

    with patch("homeassistant.components.roku.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MAIN_ENTITY_ID}, blocking=True
        )

        remote_mock.assert_called_once_with("poweron")

    with patch("homeassistant.components.roku.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PLAY_PAUSE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("play")

    with patch("homeassistant.components.roku.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("forward")

    with patch("homeassistant.components.roku.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("reverse")

    with patch("homeassistant.components.roku.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: "Home"},
            blocking=True,
        )

        remote_mock.assert_called_once_with("home")

    with patch("homeassistant.components.roku.Roku.launch") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: "Netflix"},
            blocking=True,
        )

        remote_mock.assert_called_once_with("12")


async def test_tv_services(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the media player services related to Roku TV."""
    await setup_integration(
        hass,
        aioclient_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    with patch("homeassistant.components.roku.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: TV_ENTITY_ID}, blocking=True
        )

        remote_mock.assert_called_once_with("volume_up")

    with patch("homeassistant.components.roku.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_DOWN,
            {ATTR_ENTITY_ID: TV_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("volume_down")

    with patch("homeassistant.components.roku.Roku.remote") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_MUTE,
            {ATTR_ENTITY_ID: TV_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
            blocking=True,
        )

        remote_mock.assert_called_once_with("volume_mute")

    with patch("homeassistant.components.roku.Roku.tune") as tune_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: TV_ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_CHANNEL,
                ATTR_MEDIA_CONTENT_ID: "55",
            },
            blocking=True,
        )

        tune_mock.assert_called_once_with("55")
