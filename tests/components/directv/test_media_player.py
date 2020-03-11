"""The tests for the DirecTV Media player platform."""
from datetime import datetime, timedelta
from typing import Optional

from asynctest import patch
from pytest import fixture
from requests import RequestException

from homeassistant.components.directv.media_player import (
    ATTR_MEDIA_CURRENTLY_RECORDING,
    ATTR_MEDIA_RATING,
    ATTR_MEDIA_RECORDED,
    ATTR_MEDIA_START_TIME,
)
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_SERIES_TITLE,
    ATTR_MEDIA_TITLE,
    DOMAIN as MP_DOMAIN,
    MEDIA_TYPE_TVSHOW,
    SERVICE_PLAY_MEDIA,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.directv import (
    CLIENT_ADDRESS,
    HOST,
    MOCK_GET_LOCATIONS_MULTIPLE,
    RECORDING,
    MockDirectvClass,
    setup_integration,
)

ATTR_UNIQUE_ID = "unique_id"
CLIENT_ENTITY_ID = f"{MP_DOMAIN}.bedroom_client"
MAIN_ENTITY_ID = f"{MP_DOMAIN}.main_dvr"

# pylint: disable=redefined-outer-name


@fixture
def client_dtv() -> MockDirectvClass:
    """Fixture for a client device."""
    mocked_dtv = MockDirectvClass(HOST, clientAddr=CLIENT_ADDRESS)
    mocked_dtv.attributes = RECORDING
    mocked_dtv._standby = False  # pylint: disable=protected-access
    return mocked_dtv


@fixture
def mock_now() -> datetime:
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def setup_directv(hass: HomeAssistantType) -> None:
    """Set up mock DirecTV integration."""
    with patch(
        "homeassistant.components.directv.DIRECTV", new=MockDirectvClass,
    ):
        await setup_integration(hass)


async def setup_directv_with_instance_error(hass: HomeAssistantType) -> None:
    """Set up mock DirecTV integration."""
    with patch(
        "homeassistant.components.directv.DIRECTV", new=MockDirectvClass,
    ), patch(
        "homeassistant.components.directv.DIRECTV.get_locations",
        return_value=MOCK_GET_LOCATIONS_MULTIPLE,
    ), patch(
        "homeassistant.components.directv.media_player.get_dtv_instance",
        return_value=None,
    ):
        await setup_integration(hass)


async def setup_directv_with_locations(
    hass: HomeAssistantType, client_dtv: MockDirectvClass,
) -> None:
    """Set up mock DirecTV integration."""
    with patch(
        "homeassistant.components.directv.DIRECTV", new=MockDirectvClass,
    ), patch(
        "homeassistant.components.directv.DIRECTV.get_locations",
        return_value=MOCK_GET_LOCATIONS_MULTIPLE,
    ), patch(
        "homeassistant.components.directv.media_player.get_dtv_instance",
        return_value=client_dtv,
    ):
        await setup_integration(hass)


async def async_turn_on(
    hass: HomeAssistantType, entity_id: Optional[str] = None
) -> None:
    """Turn on specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(MP_DOMAIN, SERVICE_TURN_ON, data)


async def async_turn_off(
    hass: HomeAssistantType, entity_id: Optional[str] = None
) -> None:
    """Turn off specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(MP_DOMAIN, SERVICE_TURN_OFF, data)


async def async_media_pause(
    hass: HomeAssistantType, entity_id: Optional[str] = None
) -> None:
    """Send the media player the command for pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PAUSE, data)


async def async_media_play(
    hass: HomeAssistantType, entity_id: Optional[str] = None
) -> None:
    """Send the media player the command for play/pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PLAY, data)


async def async_media_stop(
    hass: HomeAssistantType, entity_id: Optional[str] = None
) -> None:
    """Send the media player the command for stop."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_STOP, data)


async def async_media_next_track(
    hass: HomeAssistantType, entity_id: Optional[str] = None
) -> None:
    """Send the media player the command for next track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_NEXT_TRACK, data)


async def async_media_previous_track(
    hass: HomeAssistantType, entity_id: Optional[str] = None
) -> None:
    """Send the media player the command for prev track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(MP_DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, data)


async def async_play_media(
    hass: HomeAssistantType,
    media_type: str,
    media_id: str,
    entity_id: Optional[str] = None,
    enqueue: Optional[str] = None,
) -> None:
    """Send the media player the command for playing media."""
    data = {ATTR_MEDIA_CONTENT_TYPE: media_type, ATTR_MEDIA_CONTENT_ID: media_id}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if enqueue:
        data[ATTR_MEDIA_ENQUEUE] = enqueue

    await hass.services.async_call(MP_DOMAIN, SERVICE_PLAY_MEDIA, data)


async def test_setup(hass: HomeAssistantType) -> None:
    """Test setup with basic config."""
    await setup_directv(hass)
    assert hass.states.get(MAIN_ENTITY_ID)


async def test_setup_with_multiple_locations(
    hass: HomeAssistantType, client_dtv: MockDirectvClass
) -> None:
    """Test setup with basic config with client location."""
    await setup_directv_with_locations(hass, client_dtv)

    assert hass.states.get(MAIN_ENTITY_ID)
    assert hass.states.get(CLIENT_ENTITY_ID)


async def test_setup_with_instance_error(hass: HomeAssistantType) -> None:
    """Test setup with basic config with client location that results in instance error."""
    await setup_directv_with_instance_error(hass)

    assert hass.states.get(MAIN_ENTITY_ID)
    assert hass.states.async_entity_ids(MP_DOMAIN) == [MAIN_ENTITY_ID]


async def test_unique_id(hass: HomeAssistantType, client_dtv: MockDirectvClass) -> None:
    """Test unique id."""
    await setup_directv_with_locations(hass, client_dtv)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    main = entity_registry.async_get(MAIN_ENTITY_ID)
    assert main.unique_id == "028877455858"

    client = entity_registry.async_get(CLIENT_ENTITY_ID)
    assert client.unique_id == "2CA17D1CD30X"


async def test_supported_features(
    hass: HomeAssistantType, client_dtv: MockDirectvClass
) -> None:
    """Test supported features."""
    await setup_directv_with_locations(hass, client_dtv)

    # Features supported for main DVR
    state = hass.states.get(MAIN_ENTITY_ID)
    assert (
        SUPPORT_PAUSE
        | SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_STOP
        | SUPPORT_NEXT_TRACK
        | SUPPORT_PREVIOUS_TRACK
        | SUPPORT_PLAY
        == state.attributes.get("supported_features")
    )

    # Feature supported for clients.
    state = hass.states.get(CLIENT_ENTITY_ID)
    assert (
        SUPPORT_PAUSE
        | SUPPORT_PLAY_MEDIA
        | SUPPORT_STOP
        | SUPPORT_NEXT_TRACK
        | SUPPORT_PREVIOUS_TRACK
        | SUPPORT_PLAY
        == state.attributes.get("supported_features")
    )


async def test_check_attributes(
    hass: HomeAssistantType, mock_now: dt_util.dt.datetime, client_dtv: MockDirectvClass
) -> None:
    """Test attributes."""
    await setup_directv_with_locations(hass, client_dtv)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    # Start playing TV
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        await async_media_play(hass, CLIENT_ENTITY_ID)
        await hass.async_block_till_done()

    state = hass.states.get(CLIENT_ENTITY_ID)
    assert state.state == STATE_PLAYING

    assert state.attributes.get(ATTR_MEDIA_CONTENT_ID) == RECORDING["programId"]
    assert state.attributes.get(ATTR_MEDIA_CONTENT_TYPE) == MEDIA_TYPE_TVSHOW
    assert state.attributes.get(ATTR_MEDIA_DURATION) == RECORDING["duration"]
    assert state.attributes.get(ATTR_MEDIA_POSITION) == 2
    assert state.attributes.get(ATTR_MEDIA_POSITION_UPDATED_AT) == next_update
    assert state.attributes.get(ATTR_MEDIA_TITLE) == RECORDING["title"]
    assert state.attributes.get(ATTR_MEDIA_SERIES_TITLE) == RECORDING["episodeTitle"]
    assert state.attributes.get(ATTR_MEDIA_CHANNEL) == "{} ({})".format(
        RECORDING["callsign"], RECORDING["major"]
    )
    assert state.attributes.get(ATTR_INPUT_SOURCE) == RECORDING["major"]
    assert (
        state.attributes.get(ATTR_MEDIA_CURRENTLY_RECORDING) == RECORDING["isRecording"]
    )
    assert state.attributes.get(ATTR_MEDIA_RATING) == RECORDING["rating"]
    assert state.attributes.get(ATTR_MEDIA_RECORDED)
    assert state.attributes.get(ATTR_MEDIA_START_TIME) == datetime(
        2018, 11, 10, 19, 0, tzinfo=dt_util.UTC
    )

    # Test to make sure that ATTR_MEDIA_POSITION_UPDATED_AT is not
    # updated if TV is paused.
    with patch(
        "homeassistant.util.dt.utcnow", return_value=next_update + timedelta(minutes=5)
    ):
        await async_media_pause(hass, CLIENT_ENTITY_ID)
        await hass.async_block_till_done()

    state = hass.states.get(CLIENT_ENTITY_ID)
    assert state.state == STATE_PAUSED
    assert state.attributes.get(ATTR_MEDIA_POSITION_UPDATED_AT) == next_update


async def test_main_services(
    hass: HomeAssistantType, mock_now: dt_util.dt.datetime, client_dtv: MockDirectvClass
) -> None:
    """Test the different services."""
    await setup_directv_with_locations(hass, client_dtv)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
    # DVR starts in off state.
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_OFF

    # Turn main DVR on. When turning on DVR is playing.
    await async_turn_on(hass, MAIN_ENTITY_ID)
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_PLAYING

    # Pause live TV.
    await async_media_pause(hass, MAIN_ENTITY_ID)
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_PAUSED

    # Start play again for live TV.
    await async_media_play(hass, MAIN_ENTITY_ID)
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_PLAYING

    # Change channel, currently it should be 202
    assert state.attributes.get("source") == 202
    await async_play_media(hass, "channel", 7, MAIN_ENTITY_ID)
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.attributes.get("source") == 7

    # Stop live TV.
    await async_media_stop(hass, MAIN_ENTITY_ID)
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_PAUSED

    # Turn main DVR off.
    await async_turn_off(hass, MAIN_ENTITY_ID)
    await hass.async_block_till_done()
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_OFF


async def test_available(
    hass: HomeAssistantType, mock_now: dt_util.dt.datetime, client_dtv: MockDirectvClass
) -> None:
    """Test available status."""
    await setup_directv_with_locations(hass, client_dtv)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    # Confirm service is currently set to available.
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Make update fail 1st time
    next_update = next_update + timedelta(minutes=5)
    with patch(
        "homeassistant.components.directv.DIRECTV.get_standby",
        side_effect=RequestException,
    ), patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Make update fail 2nd time within 1 minute
    next_update = next_update + timedelta(seconds=30)
    with patch(
        "homeassistant.components.directv.DIRECTV.get_standby",
        side_effect=RequestException,
    ), patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Make update fail 3rd time more then a minute after 1st failure
    next_update = next_update + timedelta(minutes=1)
    with patch(
        "homeassistant.components.directv.DIRECTV.get_standby",
        side_effect=RequestException,
    ), patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    # Recheck state, update should work again.
    next_update = next_update + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE
