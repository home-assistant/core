"""Test the Devialet init."""

from unittest.mock import PropertyMock, patch

from devialet import DevialetApi
from devialet.const import UrlSuffix
from freezegun.api import FrozenDateTimeFactory
import pytest
from yarl import URL

from homeassistant.components.devialet.media_player import (
    SUPPORT_DEVIALET,
    SUPPORT_MEDIA,
)
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
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerState,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.components.websocket_api import TYPE_RESULT
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
from homeassistant.exceptions import ServiceValidationError

from . import HOST, NAME, setup_integration

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator

SERVICE_TO_URL = {
    SERVICE_MEDIA_SEEK: [UrlSuffix.SEEK],
    SERVICE_MEDIA_PLAY: [UrlSuffix.PLAY],
    SERVICE_MEDIA_PAUSE: [UrlSuffix.PAUSE],
    SERVICE_MEDIA_STOP: [UrlSuffix.PAUSE],
    SERVICE_MEDIA_PREVIOUS_TRACK: [UrlSuffix.PREVIOUS_TRACK],
    SERVICE_MEDIA_NEXT_TRACK: [UrlSuffix.NEXT_TRACK],
    SERVICE_PLAY_MEDIA: [UrlSuffix.PLAY],
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
    SERVICE_PLAY_MEDIA: [
        {
            "media_content_id": "media-source://sourced_media/abc123",
            "media_content_type": "music",
        },
    ],
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
        {ATTR_INPUT_SOURCE: "UPnP"},
    ],
}


async def test_media_player_playing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the Devialet configuration entry loading and unloading."""

    with (
        patch.object(
            DevialetApi, "upnp_available", new_callable=PropertyMock
        ) as mock_upnp_available,
        patch.object(
            DevialetApi, "playing_state", new_callable=PropertyMock
        ) as mock_playing_state,
        patch.object(
            DevialetApi, "equalizer", new_callable=PropertyMock
        ) as mock_equalizer,
        patch.object(
            DevialetApi, "night_mode", new_callable=PropertyMock
        ) as mock_night_mode,
        patch.object(DevialetApi, "source", new_callable=PropertyMock) as mock_source,
    ):
        entry = await setup_integration(hass, aioclient_mock)
        assert entry.state is ConfigEntryState.LOADED

        mock_upnp_available.return_value = True
        mock_playing_state.return_value = MediaPlayerState.PLAYING
        mock_equalizer.return_value = "flat"
        mock_night_mode.return_value = False
        mock_source.return_value = "spotifyconnect"

        freezer.tick(10)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

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
        assert len(state.attributes[ATTR_SUPPORTED_FEATURES]) == 13

        mock_playing_state.return_value = MediaPlayerState.PAUSED
        freezer.tick(10)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").state
            == MediaPlayerState.PAUSED
        )

        mock_playing_state.return_value = MediaPlayerState.ON
        freezer.tick(10)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").state == MediaPlayerState.ON
        )

        mock_equalizer.return_value = None
        mock_night_mode.return_value = True
        freezer.tick(10)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes[ATTR_SOUND_MODE]
            == "Night mode"
        )

        mock_equalizer.return_value = "unexpected_value"
        mock_night_mode.return_value = False
        freezer.tick(10)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            ATTR_SOUND_MODE
            not in hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes
        )

        mock_equalizer.return_value = None
        mock_night_mode.return_value = None
        freezer.tick(10)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            ATTR_SOUND_MODE
            not in hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes
        )

        with patch.object(
            DevialetApi, "available_operations", new_callable=PropertyMock
        ) as mock:
            mock.return_value = None
            freezer.tick(10)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert (
                hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes[
                    ATTR_SUPPORTED_FEATURES
                ]
                == SUPPORT_DEVIALET | SUPPORT_MEDIA
            )

        with patch.object(DevialetApi, "source", new_callable=PropertyMock) as mock:
            mock.return_value = "someSource"
            freezer.tick(10)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert (
                ATTR_INPUT_SOURCE
                not in hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}").attributes
            )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_media_player_offline(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet configuration entry loading and unloading."""
    entry = await setup_integration(hass, aioclient_mock, state=STATE_UNAVAILABLE)

    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get(f"{MP_DOMAIN}.{NAME.lower()}")
    assert state.state == STATE_UNAVAILABLE
    assert state.name == NAME

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_device_shutdown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet configuration entry loading and the device going offline."""
    with patch.object(
        DevialetApi, "upnp_available", new_callable=PropertyMock
    ) as mock_upnp_available:
        mock_upnp_available.return_value = True
        entry = await setup_integration(hass, aioclient_mock, serial=None)

        assert entry.state is ConfigEntryState.LOADED
        assert entry.unique_id is None

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_media_player_without_serial(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet configuration entry loading and unloading."""
    with patch.object(
        DevialetApi, "upnp_available", new_callable=PropertyMock
    ) as mock_upnp_available:
        mock_upnp_available.return_value = True
        entry = await setup_integration(hass, aioclient_mock, serial=None)

        assert entry.state is ConfigEntryState.LOADED
        assert entry.unique_id is None

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_browse_media(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the Devialet services."""

    client = await hass_ws_client(hass)
    entry = await setup_integration(
        hass, aioclient_mock, state=MediaPlayerState.PLAYING
    )
    assert entry.state is ConfigEntryState.LOADED

    with (
        patch.object(
            DevialetApi, "upnp_available", new_callable=PropertyMock
        ) as mock_upnp_available,
        patch(
            "homeassistant.components.media_source.async_browse_media",
            return_value=True,
        ) as mock_browse_media,
    ):
        mock_upnp_available.return_value = True
        await client.send_json(
            {
                "id": 5,
                "type": "media_player/browse_media",
                "entity_id": "media_player.livingroom",
                "media_content_type": "album",
                "media_content_id": "abcd",
            }
        )
        msg = await client.receive_json()

        assert msg["id"] == 5
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]
        assert msg["result"]
        assert mock_browse_media.call_count == 1


async def test_media_player_services(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Devialet exceptions."""

    with (
        patch.object(
            DevialetApi, "upnp_available", new_callable=PropertyMock
        ) as mock_upnp_available,
        patch.object(DevialetApi, "async_play_url_source"),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=PlayMedia("https://home-assistant.io/test.mp3", "music"),
        ),
    ):
        mock_upnp_available.return_value = True
        entry = await setup_integration(
            hass, aioclient_mock, state=MediaPlayerState.PLAYING
        )
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

    async def test_play_media_exceptions(
        hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
    ) -> None:
        """Test the Devialet services."""
        with (
            patch.object(
                DevialetApi, "upnp_available", new_callable=PropertyMock
            ) as mock_upnp_available,
            patch(
                "homeassistant.components.devialet.media_player.DevialetMediaPlayerEntity.supported_features",
                new_callable=PropertyMock,
            ) as mock_supported_features,
            patch.object(
                DevialetApi, "async_play_url_source", return_value=True
            ) as patch_play_url_source,
            patch(
                "homeassistant.components.media_source.async_resolve_media",
                return_value=PlayMedia("https://home-assistant.io/test.mp3", "music"),
            ),
        ):
            mock_upnp_available.return_value = True
            entry = await setup_integration(
                hass, aioclient_mock, state=MediaPlayerState.PLAYING
            )
            assert entry.state is ConfigEntryState.LOADED

            mock_upnp_available.return_value = False
            mock_supported_features.return_value = SUPPORT_MEDIA
            service_data = {
                ATTR_ENTITY_ID: hass.states.get(f"{MP_DOMAIN}.{NAME}").entity_id
            }
            service_data.update(SERVICE_TO_DATA[SERVICE_PLAY_MEDIA][0])

            with pytest.raises(ServiceValidationError):
                await hass.services.async_call(
                    MP_DOMAIN,
                    SERVICE_PLAY_MEDIA,
                    service_data=service_data,
                    blocking=True,
                )

            patch_play_url_source.return_value = False
            mock_upnp_available.return_value = True

            with pytest.raises(ServiceValidationError):
                await hass.services.async_call(
                    MP_DOMAIN,
                    SERVICE_PLAY_MEDIA,
                    service_data=service_data,
                    blocking=True,
                )

            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()

            assert entry.state is ConfigEntryState.NOT_LOADED
