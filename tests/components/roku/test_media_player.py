"""Tests for the Roku Media Player platform."""
from datetime import timedelta

from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    ReadTimeout as RequestsReadTimeout,
)
from requests_mock import Mocker
from roku import RokuException

from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
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
    SUPPORT_VOLUME_SET,
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
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from tests.async_mock import PropertyMock, patch
from tests.common import async_fire_time_changed
from tests.components.roku import UPNP_SERIAL, setup_integration

MAIN_ENTITY_ID = f"{MP_DOMAIN}.my_roku_3"
TV_ENTITY_ID = f"{MP_DOMAIN}.58_onn_roku_tv"

TV_HOST = "192.168.1.161"
TV_SERIAL = "YN00H5555555"


async def test_setup(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test setup with basic config."""
    await setup_integration(hass, requests_mock)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    main = entity_registry.async_get(MAIN_ENTITY_ID)
    assert hass.states.get(MAIN_ENTITY_ID)
    assert main.unique_id == UPNP_SERIAL


async def test_idle_setup(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test setup with idle device."""
    with patch(
        "homeassistant.components.roku.Roku.power_state",
        new_callable=PropertyMock(return_value="Off"),
    ):
        await setup_integration(hass, requests_mock)

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_STANDBY


async def test_tv_setup(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test Roku TV setup."""
    await setup_integration(
        hass,
        requests_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    tv = entity_registry.async_get(TV_ENTITY_ID)
    assert hass.states.get(TV_ENTITY_ID)
    assert tv.unique_id == TV_SERIAL


async def test_availability(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test entity availability."""
    now = dt_util.utcnow()
    future = now + timedelta(minutes=1)

    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await setup_integration(hass, requests_mock)

    with patch("roku.Roku._get", side_effect=RokuException,), patch(
        "homeassistant.util.dt.utcnow", return_value=future
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(MAIN_ENTITY_ID).state == STATE_UNAVAILABLE

    future += timedelta(minutes=1)

    with patch("roku.Roku._get", side_effect=RequestsConnectionError,), patch(
        "homeassistant.util.dt.utcnow", return_value=future
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(MAIN_ENTITY_ID).state == STATE_UNAVAILABLE

    future += timedelta(minutes=1)

    with patch("roku.Roku._get", side_effect=RequestsReadTimeout,), patch(
        "homeassistant.util.dt.utcnow", return_value=future
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(MAIN_ENTITY_ID).state == STATE_UNAVAILABLE

    future += timedelta(minutes=1)

    with patch("homeassistant.util.dt.utcnow", return_value=future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.states.get(MAIN_ENTITY_ID).state == STATE_HOME


async def test_supported_features(
    hass: HomeAssistantType, requests_mock: Mocker
) -> None:
    """Test supported features."""
    await setup_integration(hass, requests_mock)

    # Features supported for Rokus
    state = hass.states.get(MAIN_ENTITY_ID)
    assert (
        SUPPORT_PREVIOUS_TRACK
        | SUPPORT_NEXT_TRACK
        | SUPPORT_VOLUME_SET
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_SELECT_SOURCE
        | SUPPORT_PLAY
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        == state.attributes.get("supported_features")
    )


async def test_tv_supported_features(
    hass: HomeAssistantType, requests_mock: Mocker
) -> None:
    """Test supported features for Roku TV."""
    await setup_integration(
        hass,
        requests_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    state = hass.states.get(TV_ENTITY_ID)
    assert (
        SUPPORT_PREVIOUS_TRACK
        | SUPPORT_NEXT_TRACK
        | SUPPORT_VOLUME_SET
        | SUPPORT_VOLUME_MUTE
        | SUPPORT_SELECT_SOURCE
        | SUPPORT_PLAY
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        == state.attributes.get("supported_features")
    )


async def test_attributes(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test attributes."""
    await setup_integration(hass, requests_mock)

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_HOME

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) is None
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Roku"


async def test_tv_attributes(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test attributes for Roku TV."""
    await setup_integration(
        hass,
        requests_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    state = hass.states.get(TV_ENTITY_ID)
    assert state.state == STATE_PLAYING

    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MEDIA_TYPE_CHANNEL
    assert state.attributes.get(ATTR_INPUT_SOURCE) == "Antenna TV"


async def test_services(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test the different media player services."""
    await setup_integration(hass, requests_mock)

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: MAIN_ENTITY_ID}, blocking=True
        )

        remote_mock.assert_called_once_with("/keypress/PowerOff")

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: MAIN_ENTITY_ID}, blocking=True
        )

        remote_mock.assert_called_once_with("/keypress/PowerOn")

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PLAY_PAUSE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("/keypress/Play")

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("/keypress/Fwd")

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("/keypress/Rev")

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: "Home"},
            blocking=True,
        )

        remote_mock.assert_called_once_with("/keypress/Home")

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MAIN_ENTITY_ID, ATTR_INPUT_SOURCE: "Netflix"},
            blocking=True,
        )

        remote_mock.assert_called_once_with("/launch/12", params={"contentID": "12"})


async def test_tv_services(hass: HomeAssistantType, requests_mock: Mocker) -> None:
    """Test the media player services related to Roku TV."""
    await setup_integration(
        hass,
        requests_mock,
        device="rokutv",
        app="tvinput-dtv",
        host=TV_HOST,
        unique_id=TV_SERIAL,
    )

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN, SERVICE_VOLUME_UP, {ATTR_ENTITY_ID: TV_ENTITY_ID}, blocking=True
        )

        remote_mock.assert_called_once_with("/keypress/VolumeUp")

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_DOWN,
            {ATTR_ENTITY_ID: TV_ENTITY_ID},
            blocking=True,
        )

        remote_mock.assert_called_once_with("/keypress/VolumeDown")

    with patch("roku.Roku._post") as remote_mock:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_MUTE,
            {ATTR_ENTITY_ID: TV_ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
            blocking=True,
        )

        remote_mock.assert_called_once_with("/keypress/VolumeMute")

    with patch("roku.Roku.launch") as tune_mock:
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

        tune_mock.assert_called_once()
