"""DataUpdateCoordinator for the KEF integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

import aiohttp
from pykefcontrol.kef_connector import KefAsyncConnector

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

type KefConfigEntry = ConfigEntry[KefCoordinator]


@dataclass
class KefData:
    """Data from a KEF speaker update."""

    is_on: bool
    source: str
    volume: int
    is_playing: bool
    is_muted: bool
    media_title: str | None = None
    media_artist: str | None = None
    media_album: str | None = None
    media_image_url: str | None = None
    media_service: str | None = None
    audio_codec: str | None = None
    sample_rate: int | None = None
    audio_channels: int | None = None
    wifi_ssid: str | None = None
    wifi_signal: int | None = None
    wifi_frequency: int | None = None
    sound_profile: str | None = None
    profile_name: str | None = None
    dialogue_mode: bool = False
    bass_extension: str | None = None
    wall_mode: bool = False
    desk_mode: bool = False
    sub_out: bool = False
    sub_gain: int = 0
    treble: float = 0.0


class KefCoordinator(DataUpdateCoordinator[KefData]):
    """KEF speaker data update coordinator."""

    config_entry: KefConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KefConfigEntry,
        connector: KefAsyncConnector,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"KEF {config_entry.title}",
            update_interval=SCAN_INTERVAL,
        )
        self.connector = connector

    async def _get_dsp_value(self, name: str) -> dict | None:
        """Get a DSP v2 value by path."""
        try:
            result = await self.connector.get_request(
                f"settings:/kef/dsp/v2/{name}"
            )
            if result and result[0] is not None:
                return result[0]
        except (IndexError, KeyError, TypeError):
            pass
        return None

    async def set_dsp_value(self, path: str, value: dict) -> None:
        """Set a DSP v2 value."""
        payload = {
            "path": f"settings:/kef/dsp/v2/{path}",
            "roles": "value",
            "value": value,
        }
        await self.connector._set_data(payload)

    @override
    async def _async_update_data(self) -> KefData:
        """Fetch data from the KEF speaker."""
        try:
            source = await self.connector.source
            volume = await self.connector.volume
            is_on = source != "standby"
            is_playing = False
            is_muted = False
            media_title = None
            media_artist = None
            media_album = None
            media_image_url = None
            media_service = None
            audio_codec = None
            sample_rate = None
            audio_channels = None
            wifi_ssid = None
            wifi_signal = None
            wifi_frequency = None
            sound_profile = None
            profile_name = None
            dialogue_mode = False
            bass_extension = None
            wall_mode = False
            desk_mode = False
            sub_out = False
            sub_gain = 0
            treble = 0.0

            # Get mute status
            mute_data = await self.connector.get_request(
                "settings:/mediaPlayer/mute"
            )
            if mute_data:
                is_muted = mute_data[0].get("bool_", False)

            if is_on:
                is_playing = await self.connector.is_playing

                # Song info
                song_info = await self.connector.get_song_information()
                media_title = song_info.get("title")
                media_artist = song_info.get("artist")
                media_album = song_info.get("album")
                media_image_url = song_info.get("cover_url")
                media_service = song_info.get("service_id")

                # Audio codec info
                codec_info = await self.connector.get_audio_codec_information()
                audio_codec = codec_info.get("codec")
                sample_rate = codec_info.get("sampleFrequency")
                audio_channels = codec_info.get("nrAudioChannels")

            # DSP / sound profile data
            sp = await self._get_dsp_value("soundProfile")
            if sp:
                sound_profile = sp.get("string_")
            pn = await self._get_dsp_value("profileName")
            if pn:
                profile_name = pn.get("string_") or None
            dm = await self._get_dsp_value("dialogueMode")
            if dm:
                dialogue_mode = dm.get("bool_", False)
            be = await self._get_dsp_value("bassExtension")
            if be:
                bass_extension = be.get("string_")
            wm = await self._get_dsp_value("wallMode")
            if wm:
                wall_mode = wm.get("bool_", False)
            dkm = await self._get_dsp_value("deskMode")
            if dkm:
                desk_mode = dkm.get("bool_", False)
            so = await self._get_dsp_value("subwooferOut")
            if so:
                sub_out = so.get("bool_", False)
            sg = await self._get_dsp_value("subwooferGain")
            if sg:
                sub_gain = sg.get("i32_", 0)
            tr = await self._get_dsp_value("trebleAmount")
            if tr:
                treble = tr.get("double_", 0.0)

            # WiFi info
            wifi_info = await self.connector.get_wifi_information()
            wifi_ssid = wifi_info.get("ssid")
            wifi_signal = wifi_info.get("signalLevel")
            wifi_frequency = wifi_info.get("frequency")

        except (aiohttp.ClientError, TimeoutError, IndexError, KeyError) as err:
            raise UpdateFailed(
                f"Error communicating with KEF speaker: {err}"
            ) from err

        return KefData(
            is_on=is_on,
            source=source,
            volume=volume,
            is_playing=is_playing,
            is_muted=is_muted,
            media_title=media_title,
            media_artist=media_artist,
            media_album=media_album,
            media_image_url=media_image_url,
            media_service=media_service,
            audio_codec=audio_codec,
            sample_rate=sample_rate,
            audio_channels=audio_channels,
            wifi_ssid=wifi_ssid,
            wifi_signal=wifi_signal,
            wifi_frequency=wifi_frequency,
            sound_profile=sound_profile,
            profile_name=profile_name,
            dialogue_mode=dialogue_mode,
            bass_extension=bass_extension,
            wall_mode=wall_mode,
            desk_mode=desk_mode,
            sub_out=sub_out,
            sub_gain=sub_gain,
            treble=treble,
        )
