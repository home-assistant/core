"""Constants used for testing the bang_olufsen integration."""

from ipaddress import IPv4Address, IPv6Address
from unittest.mock import Mock

from mozart_api.exceptions import ApiException
from mozart_api.models import (
    Action,
    ListeningModeRef,
    OverlayPlayRequest,
    OverlayPlayRequestTextToSpeechTextToSpeech,
    PlaybackContentMetadata,
    PlaybackError,
    PlaybackProgress,
    PlayQueueItem,
    PlayQueueItemType,
    RenderingState,
    SceneProperties,
    Source,
    UserFlow,
    VolumeLevel,
    VolumeMute,
    VolumeState,
)

from homeassistant.components.bang_olufsen.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_ITEM_NUMBER,
    ATTR_SERIAL_NUMBER,
    ATTR_TYPE_NUMBER,
    CONF_BEOLINK_JID,
    BangOlufsenSource,
)
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME

TEST_HOST = "192.168.0.1"
TEST_HOST_INVALID = "192.168.0"
TEST_HOST_IPV6 = "1111:2222:3333:4444:5555:6666:7777:8888"
TEST_MODEL_BALANCE = "Beosound Balance"
TEST_MODEL_THEATRE = "Beosound Theatre"
TEST_MODEL_LEVEL = "Beosound Level"
TEST_SERIAL_NUMBER = "11111111"
TEST_SERIAL_NUMBER_2 = "22222222"
TEST_NAME = f"{TEST_MODEL_BALANCE}-{TEST_SERIAL_NUMBER}"
TEST_NAME_2 = f"{TEST_MODEL_BALANCE}-{TEST_SERIAL_NUMBER_2}"
TEST_FRIENDLY_NAME = "Living room Balance"
TEST_TYPE_NUMBER = "1111"
TEST_ITEM_NUMBER = "1111111"
TEST_JID_1 = f"{TEST_TYPE_NUMBER}.{TEST_ITEM_NUMBER}.{TEST_SERIAL_NUMBER}@products.bang-olufsen.com"
TEST_MEDIA_PLAYER_ENTITY_ID = "media_player.beosound_balance_11111111"

TEST_FRIENDLY_NAME_2 = "Laundry room Balance"
TEST_JID_2 = f"{TEST_TYPE_NUMBER}.{TEST_ITEM_NUMBER}.22222222@products.bang-olufsen.com"
TEST_MEDIA_PLAYER_ENTITY_ID_2 = "media_player.beosound_balance_22222222"
TEST_HOST_2 = "192.168.0.2"

TEST_FRIENDLY_NAME_3 = "Lego room Balance"
TEST_JID_3 = f"{TEST_TYPE_NUMBER}.{TEST_ITEM_NUMBER}.33333333@products.bang-olufsen.com"
TEST_MEDIA_PLAYER_ENTITY_ID_3 = "media_player.beosound_balance_33333333"
TEST_HOST_3 = "192.168.0.3"

TEST_FRIENDLY_NAME_4 = "Lounge room Balance"
TEST_JID_4 = f"{TEST_TYPE_NUMBER}.{TEST_ITEM_NUMBER}.44444444@products.bang-olufsen.com"
TEST_MEDIA_PLAYER_ENTITY_ID_4 = "media_player.beosound_balance_44444444"
TEST_HOST_4 = "192.168.0.4"

TEST_HOSTNAME_ZEROCONF = TEST_NAME.replace(" ", "-") + ".local."
TEST_TYPE_ZEROCONF = "_bangolufsen._tcp.local."
TEST_NAME_ZEROCONF = TEST_NAME.replace(" ", "-") + "." + TEST_TYPE_ZEROCONF

TEST_DATA_USER = {CONF_HOST: TEST_HOST, CONF_MODEL: TEST_MODEL_BALANCE}
TEST_DATA_USER_INVALID = {CONF_HOST: TEST_HOST_INVALID, CONF_MODEL: TEST_MODEL_BALANCE}


TEST_DATA_CREATE_ENTRY = {
    CONF_HOST: TEST_HOST,
    CONF_MODEL: TEST_MODEL_BALANCE,
    CONF_BEOLINK_JID: TEST_JID_1,
    CONF_NAME: TEST_NAME,
}
TEST_DATA_CREATE_ENTRY_2 = {
    CONF_HOST: TEST_HOST,
    CONF_MODEL: TEST_MODEL_BALANCE,
    CONF_BEOLINK_JID: TEST_JID_2,
    CONF_NAME: TEST_NAME_2,
}

TEST_DATA_ZEROCONF = ZeroconfServiceInfo(
    ip_address=IPv4Address(TEST_HOST),
    ip_addresses=[IPv4Address(TEST_HOST)],
    port=80,
    hostname=TEST_HOSTNAME_ZEROCONF,
    type=TEST_TYPE_ZEROCONF,
    name=TEST_NAME_ZEROCONF,
    properties={
        ATTR_FRIENDLY_NAME: TEST_FRIENDLY_NAME,
        ATTR_SERIAL_NUMBER: TEST_SERIAL_NUMBER,
        ATTR_TYPE_NUMBER: TEST_TYPE_NUMBER,
        ATTR_ITEM_NUMBER: TEST_ITEM_NUMBER,
    },
)

TEST_DATA_ZEROCONF_NOT_MOZART = ZeroconfServiceInfo(
    ip_address=IPv4Address(TEST_HOST),
    ip_addresses=[IPv4Address(TEST_HOST)],
    port=80,
    hostname=TEST_HOSTNAME_ZEROCONF,
    type=TEST_TYPE_ZEROCONF,
    name=TEST_NAME_ZEROCONF,
    properties={ATTR_SERIAL_NUMBER: TEST_SERIAL_NUMBER},
)

TEST_DATA_ZEROCONF_IPV6 = ZeroconfServiceInfo(
    ip_address=IPv6Address(TEST_HOST_IPV6),
    ip_addresses=[IPv6Address(TEST_HOST_IPV6)],
    port=80,
    hostname=TEST_HOSTNAME_ZEROCONF,
    type=TEST_TYPE_ZEROCONF,
    name=TEST_NAME_ZEROCONF,
    properties={
        ATTR_FRIENDLY_NAME: TEST_FRIENDLY_NAME,
        ATTR_SERIAL_NUMBER: TEST_SERIAL_NUMBER,
        ATTR_TYPE_NUMBER: TEST_TYPE_NUMBER,
        ATTR_ITEM_NUMBER: TEST_ITEM_NUMBER,
    },
)

TEST_SOURCE = Source(
    name="Tidal", id="tidal", is_seekable=True, is_enabled=True, is_playable=True
)
TEST_AUDIO_SOURCES = [TEST_SOURCE.name, BangOlufsenSource.LINE_IN.name]
TEST_VIDEO_SOURCES = ["HDMI A"]
TEST_SOURCES = TEST_AUDIO_SOURCES + TEST_VIDEO_SOURCES
TEST_FALLBACK_SOURCES = [
    "Audio Streamer",
    "Bluetooth",
    "Spotify Connect",
    "Line-In",
    "Optical",
    "B&O Radio",
    "Deezer",
    "Tidal Connect",
]
TEST_PLAYBACK_METADATA = PlaybackContentMetadata(
    album_name="Test album",
    artist_name="Test artist",
    organization="Test organization",
    title="Test title",
    total_duration_seconds=123,
    track=1,
)
TEST_PLAYBACK_ERROR = PlaybackError(error="Test error")
TEST_PLAYBACK_PROGRESS = PlaybackProgress(progress=123)
TEST_PLAYBACK_STATE_PAUSED = RenderingState(value="paused")
TEST_PLAYBACK_STATE_PLAYING = RenderingState(value="started")
TEST_VOLUME = VolumeState(level=VolumeLevel(level=40))
TEST_VOLUME_HOME_ASSISTANT_FORMAT = 0.4
TEST_PLAYBACK_STATE_TURN_OFF = RenderingState(value="stopped")
TEST_VOLUME_MUTED = VolumeState(
    muted=VolumeMute(muted=True), level=VolumeLevel(level=40)
)
TEST_VOLUME_MUTED_HOME_ASSISTANT_FORMAT = True
TEST_SEEK_POSITION_HOME_ASSISTANT_FORMAT = 10.0
TEST_SEEK_POSITION = 10000
TEST_OVERLAY_INVALID_OFFSET_VOLUME_TTS = OverlayPlayRequest(
    text_to_speech=OverlayPlayRequestTextToSpeechTextToSpeech(
        lang="da-dk", text="Dette er en test"
    )
)
TEST_OVERLAY_OFFSET_VOLUME_TTS = OverlayPlayRequest(
    text_to_speech=OverlayPlayRequestTextToSpeechTextToSpeech(
        lang="en-us", text="This is a test"
    ),
    volume_absolute=60,
)
TEST_RADIO_STATION = SceneProperties(
    action_list=[
        Action(
            type="radio",
            radio_station_id="1234567890123456",
        )
    ]
)
TEST_DEEZER_FLOW = UserFlow(user_id="123")
TEST_DEEZER_PLAYLIST = PlayQueueItem(
    provider=PlayQueueItemType(value="deezer"),
    start_now_from_position=123,
    type="playlist",
    uri="playlist:1234567890",
)
TEST_DEEZER_TRACK = PlayQueueItem(
    provider=PlayQueueItemType(value="deezer"),
    start_now_from_position=0,
    type="track",
    uri="1234567890",
)

# codespell can't see the escaped ', so it thinks the word is misspelled
TEST_DEEZER_INVALID_FLOW = ApiException(
    status=400,
    reason="Bad Request",
    http_resp=Mock(
        status=400,
        reason="Bad Request",
        data='{"message": "Couldn\'t start user flow for me"}',  # codespell:ignore
    ),
)
TEST_SOUND_MODE = 123
TEST_SOUND_MODE_2 = 234
TEST_SOUND_MODE_NAME = "Test Listening Mode"
TEST_ACTIVE_SOUND_MODE_NAME = f"{TEST_SOUND_MODE_NAME} ({TEST_SOUND_MODE})"
TEST_ACTIVE_SOUND_MODE_NAME_2 = f"{TEST_SOUND_MODE_NAME} ({TEST_SOUND_MODE_2})"
TEST_LISTENING_MODE_REF = ListeningModeRef(href="", id=TEST_SOUND_MODE_2)
TEST_SOUND_MODES = [
    TEST_ACTIVE_SOUND_MODE_NAME,
    TEST_ACTIVE_SOUND_MODE_NAME_2,
    f"{TEST_SOUND_MODE_NAME} 2 (345)",
]
