"""Test the Devialet init."""

from unittest.mock import PropertyMock, patch

from devialet import DevialetApi
from devialet.const import UrlSuffix
from yarl import URL

from homeassistant.components.devialet.const import DOMAIN
from homeassistant.components.devialet.media_player import SUPPORT_DEVIALET
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MP_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import HOST, NAME, setup_integration

from tests.test_util.aiohttp import AiohttpClientMocker

SERVICE_TO_URL = {
    SERVICE_MEDIA_SEEK: [UrlSuffix.SEEK],
    SERVICE_MEDIA_PLAY: [UrlSuffix.PLAY],
    SERVICE_MEDIA_PAUSE: [UrlSuffix.PAUSE],
    SERVICE_MEDIA_STOP: [UrlSuffix.PAUSE],
    SERVICE_MEDIA_PREVIOUS_TRACK: [UrlSuffix.PREVIOUS_TRACK],
    SERVICE_MEDIA_NEXT_TRACK: [UrlSuffix.NEXT_TRACK],
    SERVICE_TURN_OFF: [UrlSuffix.TURN_OFF],
    SERVICE_VOLUME_UP: [UrlSuffix.VOLUME_UP],
    SERVICE_VOLUME_DOWN: [UrlSuffix.VOLUME_DOWN],
    SERVICE_VOLUME_SET: [UrlSuffix.VOLUME_SET],
    SERVICE_VOLUME_MUTE: [UrlSuffix.MUTE, UrlSuffix.UNMUTE],
    SERVICE_SELECT_SOUND_MODE: [UrlSuffix.EQUALIZER, UrlSuffix.NIGHT_MODE],
    SERVICE_SELECT_SOURCE: [
        str(UrlSuffix.SELECT_SOURCE).replace(
            "%SOURCE_ID%", "82834351-8255-4e2e-9ce2-b7d4da0aa3b0"
        ),
        str(UrlSuffix.SELECT_SOURCE).replace(
            "%SOURCE_ID%", "07b1bf6d-9216-4a7b-8d53-5590cee21d90"
        ),
    ],
}

SERVICE_TO_DATA = {
    SERVICE_MEDIA_SEEK: [{"seek_position": 321}],
    SERVICE_MEDIA_PLAY: [{}],
    SERVICE_MEDIA_PAUSE: [{}],
    SERVICE_MEDIA_STOP: [{}],
    SERVICE_MEDIA_PREVIOUS_TRACK: [{}],
    SERVICE_MEDIA_NEXT_TRACK: [{}],
    SERVICE_TURN_OFF: [{}],
    SERVICE_VOLUME_UP: [{}],
    SERVICE_VOLUME_DOWN: [{}],
    SERVICE_VOLUME_SET: [{ATTR_MEDIA_VOLUME_LEVEL: 0.5}],
    SERVICE_VOLUME_MUTE: [
        {ATTR_MEDIA_VOLUME_MUTED: True},
        {ATTR_MEDIA_VOLUME_MUTED: False},
    ],
    SERVICE_SELECT_SOUND_MODE: [
        {ATTR_SOUND_MODE: "Night mode"},
        {ATTR_SOUND_MODE: "Flat"},
    ],
    SERVICE_SELECT_SOURCE: [
        {ATTR_INPUT_SOURCE: "Optical left"},
        {ATTR_INPUT_SOURCE: "Online"},
    ],
}


async def test_media_player_playing(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet configuration entry loading and unloading."""
    await async_setup_component(hass, "homeassistant", {})
    entry = await setup_integration(hass, aioclient_mock)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [f"{MP_DOMAIN}.{NAME.lower()}"]},
        blocking=True,
    )

    state = hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}")
    assert state.state == MediaPlayerState.PLAYING
    assert state.name == NAME
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.2
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] is not None
    assert state.attributes[ATTR_SOUND_MODE_LIST] is not None
    assert state.attributes[ATTR_MEDIA_ARTIST] == "The Beatles"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "1 (Remastered)"
    assert state.attributes[ATTR_MEDIA_TITLE] == "Hey Jude - Remastered 2015"
    assert state.attributes[ATTR_ENTITY_PICTURE] is not None
    assert state.attributes[ATTR_MEDIA_DURATION] == 425653
    assert state.attributes[ATTR_MEDIA_POSITION] == 123102
    assert state.attributes[ATTR_MEDIA_POSITION_UPDATED_AT] is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] is not None
    assert state.attributes[ATTR_INPUT_SOURCE] is not None
    assert state.attributes[ATTR_SOUND_MODE] is not None

    with patch(
        "homeassistant.components.devialet.DevialetApi.playing_state",
        new_callable=PropertyMock,
    ) as mock:
        mock.return_value = MediaPlayerState.PAUSED

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert (
            hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").state
            == MediaPlayerState.PAUSED
        )

    with patch(
        "homeassistant.components.devialet.DevialetApi.playing_state",
        new_callable=PropertyMock,
    ) as mock:
        mock.return_value = MediaPlayerState.ON

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert (
            hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").state == MediaPlayerState.ON
        )

    with patch.object(DevialetApi, "equalizer", new_callable=PropertyMock) as mock:
        mock.return_value = None

        with patch.object(DevialetApi, "night_mode", new_callable=PropertyMock) as mock:
            mock.return_value = True

            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            assert (
                hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes[
                    ATTR_SOUND_MODE
                ]
                == "Night mode"
            )

    with patch.object(DevialetApi, "equalizer", new_callable=PropertyMock) as mock:
        mock.return_value = "unexpected_value"

        with patch.object(DevialetApi, "night_mode", new_callable=PropertyMock) as mock:
            mock.return_value = False

            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            assert (
                ATTR_SOUND_MODE
                not in hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes
            )

    with patch.object(DevialetApi, "equalizer", new_callable=PropertyMock) as mock:
        mock.return_value = None

        with patch.object(DevialetApi, "night_mode", new_callable=PropertyMock) as mock:
            mock.return_value = None

            await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            assert (
                ATTR_SOUND_MODE
                not in hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes
            )

    with patch.object(
        DevialetApi, "available_options", new_callable=PropertyMock
    ) as mock:
        mock.return_value = None
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert (
            hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes[
                ATTR_SUPPORTED_FEATURES
            ]
            == SUPPORT_DEVIALET
        )

    with patch.object(DevialetApi, "source", new_callable=PropertyMock) as mock:
        mock.return_value = "someSource"
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert (
            ATTR_INPUT_SOURCE
            not in hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_media_player_offline(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet configuration entry loading and unloading."""
    entry = await setup_integration(hass, aioclient_mock, state=STATE_UNAVAILABLE)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}")
    assert state.state == STATE_UNAVAILABLE
    assert state.name == NAME

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_media_player_without_serial(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet configuration entry loading and unloading."""
    entry = await setup_integration(hass, aioclient_mock, serial=None)

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id is None

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_media_player_services(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet services."""
    entry = await setup_integration(
        hass, aioclient_mock, state=MediaPlayerState.PLAYING
    )

    assert entry.entry_id in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.LOADED

    target = {ATTR_ENTITY_ID: hass.states.get(f"{MP_DOMAIN}.{NAME}").entity_id}

    for i, (service, urls) in enumerate(SERVICE_TO_URL.items()):
        for url in urls:
            aioclient_mock.post(f"http://{HOST}{url}")

        for data_set in list(SERVICE_TO_DATA.values())[i]:
            service_data = target.copy()
            service_data.update(data_set)

            await hass.services.async_call(
                MP_DOMAIN,
                service,
                service_data=service_data,
                blocking=True,
            )
            await hass.async_block_till_done()

        for url in urls:
            call_available = False
            for item in aioclient_mock.mock_calls:
                if item[0] == "POST" and item[1] == URL(f"http://{HOST}{url}"):
                    call_available = True
                    break

            assert call_available

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
    assert entry.state is ConfigEntryState.NOT_LOADED
