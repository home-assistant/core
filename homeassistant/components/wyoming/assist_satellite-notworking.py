"""Wyoming satellite entity platform."""
import asyncio
import io
import logging
import wave

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.event import Event, async_write_event
from wyoming.wake import Detection
from wyoming.info import Describe, Info
from homeassistant.components.assist_pipeline.pipeline import PipelineEvent

from homeassistant.components.assist_satellite import (
    AssistSatelliteAnnouncement,
    AssistSatelliteEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, WYOMING_CLIENT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wyoming satellite from a config entry."""
    client: AsyncTcpClient = hass.data[DOMAIN][entry.entry_id][WYOMING_CLIENT]
    
    # Describe server to ensure it's a satellite
    await client.write_event(Describe().event())
    server_info_event = await client.read_event()
    if server_info_event is None:
        _LOGGER.warning("Did not receive info from satellite")
        return

    server_info = Info.from_event(server_info_event)
    if not (server_info.asr and server_info.tts):
        _LOGGER.debug("Not a satellite: %s", server_info)
        return

    satellite_entity = WyomingSatellite(entry, client)
    async_add_entities([satellite_entity])


class WyomingSatellite(AssistSatelliteEntity):
    """Wyoming satellite entity."""

    def __init__(self, entry: ConfigEntry, client: AsyncTcpClient) -> None:
        """Initialize a Wyoming satellite."""
        self.client = client
        self.client.event_callback = self.handle_event
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
        }
        self._attr_supported_features = 1

        # Task to handle events from the satellite
        self._handle_events_task = asyncio.create_task(
            self.client.run(), name=f"wyoming event handler {entry.title}"
        )

    @callback
    def handle_event(self, event: Event) -> None:
        """Handle events from the satellite."""
        # This can be expanded later if needed
        _LOGGER.debug("Received event from satellite: %s", event)

    @property
    def available(self) -> bool:
        """Return if the satellite is connected."""
        return self.client.connected

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the event handling task when the entity is removed."""
        self._handle_events_task.cancel()
        await super().async_will_remove_from_hass()
    
    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Handle pipeline events."""
        # No-op for now, but required by the base class
        _LOGGER.debug("Pipeline event: %s", event)

    async def _play_media(self, media_url: str) -> None:
        """Fetch audio from a URL and stream it to the satellite."""
        if not self.client.connected:
            _LOGGER.warning("No satellite connection to play media")
            return

        try:
            session = self.hass.helpers.aiohttp_client.async_get_clientsession()
            async with session.get(media_url) as resp:
                if resp.status != 200:
                    _LOGGER.error(
                        "Error fetching media %s: %s", media_url, resp.status
                    )
                    return

                audio_bytes = await resp.read()
                with io.BytesIO(audio_bytes) as audio_io:
                    with wave.open(audio_io, "rb") as wav_file:
                        rate = wav_file.getframerate()
                        width = wav_file.getsampwidth()
                        channels = wav_file.getnchannels()
                        chunk_size = 1024

                        await async_write_event(
                            AudioStart(rate=rate, width=width, channels=channels).event(),
                            self.client.writer,
                        )

                        while True:
                            chunk = wav_file.readframes(chunk_size)
                            if not chunk:
                                break
                            await async_write_event(
                                AudioChunk(rate=rate, width=width, channels=channels, audio=chunk).event(),
                                self.client.writer,
                            )

                        await async_write_event(AudioStop().event(), self.client.writer)
        except Exception:
            _LOGGER.exception("Error playing media: %s", media_url)

    async def async_announce(self, announcement: AssistSatelliteAnnouncement) -> None:
        """Announce media on the satellite."""
        _LOGGER.debug("Announce: %s", announcement.message)
        if announcement.preannounce_media_id:
            await self._play_media(announcement.preannounce_media_id)

        await self._play_media(announcement.media_id)
        self.tts_response_finished()

    async def async_start_conversation(
        self, start_announcement: AssistSatelliteAnnouncement
    ) -> None:
        """Start a conversation from the satellite."""
        _LOGGER.debug("Start conversation: %s", start_announcement.message)
        if start_announcement.preannounce_media_id:
            await self._play_media(start_announcement.preannounce_media_id)

        await self._play_media(start_announcement.media_id)

        # Send fake wake word detection to start listening
        if self.client.writer is not None:
            _LOGGER.debug("Sending command to start listening")
            await async_write_event(
                Detection(name="command_start").event(), self.client.writer
            )