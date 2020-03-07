"""The tests for the DirecTV Media player platform."""
from datetime import datetime, timedelta
from typing import Dict, Optional
from unittest.mock import call

from asynctest import patch
from pytest import fixture
from requests import RequestException

from homeassistant.components.directv.media_player import (
    ATTR_MEDIA_CURRENTLY_RECORDING,
    ATTR_MEDIA_RATING,
    ATTR_MEDIA_RECORDED,
    ATTR_MEDIA_START_TIME,
    DEFAULT_DEVICE,
    DOMAIN,
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
    CONF_HOST,
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
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

ATTR_UNIQUE_ID = "unique_id"
CLIENT_ENTITY_ID = f"{MP_DOMAIN}.bedroom_client"
CLIENT_NAME = "Bedroom Client"
CLIENT_ADDRESS = "2CA17D1CD30X"
MAIN_ENTITY_ID = f"{MP_DOMAIN}.main_dvr"
MAIN_NAME = "Main DVR"
IP_ADDRESS = "127.0.0.1"

LIVE = {
    "callsign": "HASSTV",
    "date": "20181110",
    "duration": 3600,
    "isOffAir": False,
    "isPclocked": 1,
    "isPpv": False,
    "isRecording": False,
    "isVod": False,
    "major": 202,
    "minor": 65535,
    "offset": 1,
    "programId": "102454523",
    "rating": "No Rating",
    "startTime": 1541876400,
    "stationId": 3900947,
    "title": "Using Home Assistant to automate your home",
}

RECORDING = {
    "callsign": "HASSTV",
    "date": "20181110",
    "duration": 3600,
    "isOffAir": False,
    "isPclocked": 1,
    "isPpv": False,
    "isRecording": True,
    "isVod": False,
    "major": 202,
    "minor": 65535,
    "offset": 1,
    "programId": "102454523",
    "rating": "No Rating",
    "startTime": 1541876400,
    "stationId": 3900947,
    "title": "Using Home Assistant to automate your home",
    "uniqueId": "12345",
    "episodeTitle": "Configure DirecTV platform.",
}

MOCK_CONFIG = {DOMAIN: [{CONF_HOST: IP_ADDRESS}]}

MOCK_GET_LOCATIONS = {
    "locations": [{"locationName": MAIN_NAME, "clientAddr": DEFAULT_DEVICE}],
    "status": {
        "code": 200,
        "commandResult": 0,
        "msg": "OK.",
        "query": "/info/getLocations",
    },
}

MOCK_GET_LOCATIONS_MULTIPLE = {
    "locations": [
        {"locationName": MAIN_NAME, "clientAddr": DEFAULT_DEVICE},
        {"locationName": CLIENT_NAME, "clientAddr": CLIENT_ADDRESS},
    ],
    "status": {
        "code": 200,
        "commandResult": 0,
        "msg": "OK.",
        "query": "/info/getLocations",
    },
}

MOCK_GET_VERSION = {
    "accessCardId": "0021-1495-6572",
    "receiverId": "0288 7745 5858",
    "status": {
        "code": 200,
        "commandResult": 0,
        "msg": "OK.",
        "query": "/info/getVersion",
    },
    "stbSoftwareVersion": "0x4ed7",
    "systemTime": 1281625203,
    "version": "1.2",
}

# pylint: disable=redefined-outer-name


class MockDirectvClass:
    """A fake DirecTV DVR device."""

    def __init__(self, ip, port=8080, clientAddr="0"):
        """Initialize the fake DirecTV device."""
        self._host = ip
        self._port = port
        self._device = clientAddr
        self._standby = True
        self._play = False

        self.attributes = LIVE

    def get_locations(self):
        """Mock for get_locations method."""
        return MOCK_GET_LOCATIONS

    def get_serial_num(self):
        """Mock for get_serial_num method."""
        test_serial_num = {
            "serialNum": "9999999999",
            "status": {
                "code": 200,
                "commandResult": 0,
                "msg": "OK.",
                "query": "/info/getSerialNum",
            },
        }

        return test_serial_num

    def get_standby(self):
        """Mock for get_standby method."""
        return self._standby

    def get_tuned(self):
        """Mock for get_tuned method."""
        if self._play:
            self.attributes["offset"] = self.attributes["offset"] + 1

        test_attributes = self.attributes
        test_attributes["status"] = {
            "code": 200,
            "commandResult": 0,
            "msg": "OK.",
            "query": "/tv/getTuned",
        }
        return test_attributes

    def get_version(self):
        """Mock for get_version method."""
        return MOCK_GET_VERSION

    def key_press(self, keypress):
        """Mock for key_press method."""
        if keypress == "poweron":
            self._standby = False
            self._play = True
        elif keypress == "poweroff":
            self._standby = True
            self._play = False
        elif keypress == "play":
            self._play = True
        elif keypress == "pause" or keypress == "stop":
            self._play = False

    def tune_channel(self, source):
        """Mock for tune_channel method."""
        self.attributes["major"] = int(source)


@fixture
def client_dtv() -> MockDirectvClass:
    """Fixture for a client device."""
    mocked_dtv = MockDirectvClass(IP_ADDRESS, clientAddr=CLIENT_ADDRESS)
    mocked_dtv.attributes = RECORDING
    mocked_dtv._standby = False  # pylint: disable=protected-access
    return mocked_dtv


@fixture
def main_dtv() -> MockDirectvClass:
    """Fixture for main DVR."""
    return MockDirectvClass(IP_ADDRESS)


@fixture
def mock_now() -> datetime:
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def setup_directv(
    hass: HomeAssistantType, config: Dict, main_dtv: MockDirectvClass
) -> None:
    """Set up mock DirecTV integration."""
    with patch(
        "homeassistant.components.directv.config_flow.get_ip", return_value=IP_ADDRESS
    ), patch(
        "homeassistant.components.directv.config_flow.get_dtv_version",
        return_value=MOCK_GET_VERSION,
    ), patch(
        "homeassistant.components.directv.get_dtv_instance", return_value=main_dtv,
    ), patch(
        "homeassistant.components.directv.get_dtv_locations",
        return_value=MOCK_GET_LOCATIONS,
    ), patch(
        "homeassistant.components.directv.get_dtv_version",
        return_value=MOCK_GET_VERSION,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()


async def setup_directv_with_instance_error(
    hass: HomeAssistantType,
    config: Dict,
    main_dtv: MockDirectvClass,
    client_dtv: Optional[MockDirectvClass] = None,
) -> None:
    """Set up mock DirecTV integration."""
    with patch(
        "homeassistant.components.directv.config_flow.get_ip", return_value=IP_ADDRESS
    ), patch(
        "homeassistant.components.directv.config_flow.get_dtv_version",
        return_value=MOCK_GET_VERSION,
    ), patch(
        "homeassistant.components.directv.get_dtv_instance", return_value=main_dtv,
    ), patch(
        "homeassistant.components.directv.get_dtv_locations",
        return_value=MOCK_GET_LOCATIONS_MULTIPLE,
    ), patch(
        "homeassistant.components.directv.get_dtv_version",
        return_value=MOCK_GET_VERSION,
    ), patch(
        "homeassistant.components.directv.media_player.get_dtv_instance",
        return_value=None,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()


async def setup_directv_with_locations(
    hass: HomeAssistantType,
    config: Dict,
    main_dtv: MockDirectvClass,
    client_dtv: Optional[MockDirectvClass] = None,
) -> None:
    """Set up mock DirecTV integration."""
    with patch(
        "homeassistant.components.directv.config_flow.get_ip", return_value=IP_ADDRESS
    ), patch(
        "homeassistant.components.directv.config_flow.get_dtv_version",
        return_value=MOCK_GET_VERSION,
    ), patch(
        "homeassistant.components.directv.get_dtv_instance", return_value=main_dtv,
    ), patch(
        "homeassistant.components.directv.get_dtv_locations",
        return_value=MOCK_GET_LOCATIONS_MULTIPLE,
    ), patch(
        "homeassistant.components.directv.get_dtv_version",
        return_value=MOCK_GET_VERSION,
    ), patch(
        "homeassistant.components.directv.media_player.get_dtv_instance",
        return_value=client_dtv,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()


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


async def test_setup(hass: HomeAssistantType, main_dtv) -> None:
    """Test setup with basic config."""
    await setup_directv(hass, MOCK_CONFIG, main_dtv)
    assert hass.states.get(MAIN_ENTITY_ID)


async def test_setup_with_multiple_locations(
    hass: HomeAssistantType, main_dtv: MockDirectvClass, client_dtv: MockDirectvClass
) -> None:
    """Test setup with basic config with client location."""
    await setup_directv_with_locations(hass, MOCK_CONFIG, main_dtv, client_dtv)

    assert hass.states.get(MAIN_ENTITY_ID)
    assert hass.states.get(CLIENT_ENTITY_ID)


async def test_setup_with_instance_error(
    hass: HomeAssistantType, main_dtv: MockDirectvClass, client_dtv: MockDirectvClass
) -> None:
    """Test setup with basic config with client location that results in instance error."""
    await setup_directv_with_instance_error(hass, MOCK_CONFIG, main_dtv, client_dtv)

    assert hass.states.get(MAIN_ENTITY_ID)
    assert hass.states.async_entity_ids(MP_DOMAIN) == [MAIN_ENTITY_ID]


async def test_unique_id(
    hass: HomeAssistantType, main_dtv: MockDirectvClass, client_dtv: MockDirectvClass
) -> None:
    """Test unique id."""
    await setup_directv_with_locations(hass, MOCK_CONFIG, main_dtv, client_dtv)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    main = entity_registry.async_get(MAIN_ENTITY_ID)
    assert main.unique_id == "028877455858"

    client = entity_registry.async_get(CLIENT_ENTITY_ID)
    assert client.unique_id == "2CA17D1CD30X"


async def test_supported_features(
    hass: HomeAssistantType, main_dtv: MockDirectvClass, client_dtv: MockDirectvClass
) -> None:
    """Test supported features."""
    await setup_directv_with_locations(hass, MOCK_CONFIG, main_dtv, client_dtv)

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
    hass: HomeAssistantType,
    mock_now: dt_util.dt.datetime,
    main_dtv: MockDirectvClass,
    client_dtv: MockDirectvClass,
) -> None:
    """Test attributes."""
    await setup_directv_with_locations(hass, MOCK_CONFIG, main_dtv, client_dtv)

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
    hass: HomeAssistantType,
    mock_now: dt_util.dt.datetime,
    main_dtv: MockDirectvClass,
    client_dtv: MockDirectvClass,
) -> None:
    """Test the different services."""
    await setup_directv_with_locations(hass, MOCK_CONFIG, main_dtv, client_dtv)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
    # DVR starts in off state.
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_OFF

    # All these should call key_press in our class.
    with patch.object(
        main_dtv, "key_press", wraps=main_dtv.key_press
    ) as mock_key_press, patch.object(
        main_dtv, "tune_channel", wraps=main_dtv.tune_channel
    ) as mock_tune_channel, patch.object(
        main_dtv, "get_tuned", wraps=main_dtv.get_tuned
    ) as mock_get_tuned, patch.object(
        main_dtv, "get_standby", wraps=main_dtv.get_standby
    ) as mock_get_standby:

        # Turn main DVR on. When turning on DVR is playing.
        await async_turn_on(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call("poweron")
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PLAYING

        # Pause live TV.
        await async_media_pause(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call("pause")
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PAUSED

        # Start play again for live TV.
        await async_media_play(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call("play")
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PLAYING

        # Change channel, currently it should be 202
        assert state.attributes.get("source") == 202
        await async_play_media(hass, "channel", 7, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_tune_channel.called
        assert mock_tune_channel.call_args == call("7")
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.attributes.get("source") == 7

        # Stop live TV.
        await async_media_stop(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call("stop")
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PAUSED

        # Turn main DVR off.
        await async_turn_off(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call("poweroff")
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_OFF

        # There should have been 6 calls to check if DVR is in standby
        assert main_dtv.get_standby.call_count == 6
        assert mock_get_standby.call_count == 6
        # There should be 5 calls to get current info (only 1 time it will
        # not be called as DVR is in standby.)
        assert main_dtv.get_tuned.call_count == 5
        assert mock_get_tuned.call_count == 5


async def test_available(
    hass: HomeAssistantType,
    mock_now: dt_util.dt.datetime,
    main_dtv: MockDirectvClass,
    client_dtv: MockDirectvClass,
) -> None:
    """Test available status."""
    await setup_directv_with_locations(hass, MOCK_CONFIG, main_dtv, client_dtv)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    # Confirm service is currently set to available.
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Make update fail 1st time
    next_update = next_update + timedelta(minutes=5)
    with patch.object(main_dtv, "get_standby", side_effect=RequestException), patch(
        "homeassistant.util.dt.utcnow", return_value=next_update
    ):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Make update fail 2nd time within 1 minute
    next_update = next_update + timedelta(seconds=30)
    with patch.object(main_dtv, "get_standby", side_effect=RequestException), patch(
        "homeassistant.util.dt.utcnow", return_value=next_update
    ):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Make update fail 3rd time more then a minute after 1st failure
    next_update = next_update + timedelta(minutes=1)
    with patch.object(main_dtv, "get_standby", side_effect=RequestException), patch(
        "homeassistant.util.dt.utcnow", return_value=next_update
    ):
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
