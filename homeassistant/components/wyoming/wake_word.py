"""Support for Wyoming wake-word-detection services."""

import asyncio
from collections.abc import AsyncIterable
import logging
from typing import override

from wyoming.audio import AudioChunk, AudioStart
from wyoming.client import AsyncTcpClient
from wyoming.error import Error
from wyoming.info import WakeProgram
from wyoming.wake import Detect, Detection

from homeassistant.components import wake_word
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WyomingInfoCoordinator
from .data import WyomingService
from .error import WyomingError, error_event_message
from .models import WyomingConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WyomingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wyoming wake-word-detection."""
    item = config_entry.runtime_data
    async_add_entities(
        [
            WyomingWakeWordProvider(hass, config_entry, item.coordinator, item.service),
        ]
    )


class WyomingWakeWordProvider(wake_word.WakeWordDetectionEntity):
    """Wyoming wake-word-detection provider."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WyomingConfigEntry,
        coordinator: WyomingInfoCoordinator,
        service: WyomingService,
    ) -> None:
        """Set up provider."""
        self.hass = hass
        self.coordinator = coordinator
        self.service = service

        # The platform is only set up when an installed wake service exists.
        wake_service = next(wake for wake in service.info.wake if wake.installed)
        self._supported_wake_words: list[wake_word.WakeWord] = []
        self._rebuild_wake_words(wake_service)

        self._attr_name = wake_service.name
        self._attr_unique_id = f"{config_entry.entry_id}-wake_word"  # pylint: disable=home-assistant-entity-unique-id-redundant-platform

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to info updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_info_update)
        )

    @callback
    def _handle_info_update(self) -> None:
        """Rebuild the wake word list when the service reports new info."""
        wake_service = next(
            (wake for wake in self.coordinator.data.wake if wake.installed), None
        )
        if wake_service is None:
            # Keep the last known wake words if the service reports none.
            return

        self._rebuild_wake_words(wake_service)

    @callback
    def _rebuild_wake_words(self, wake_service: WakeProgram) -> None:
        """Collect the wake words offered by the service."""
        self._supported_wake_words = [
            wake_word.WakeWord(
                id=ww.name, name=ww.description or ww.name, phrase=ww.phrase
            )
            for ww in wake_service.models
        ]

    @override
    async def get_supported_wake_words(self) -> list[wake_word.WakeWord]:
        """Return a list of supported wake words."""
        return self._supported_wake_words

    @override
    async def _async_process_audio_stream(
        self, stream: AsyncIterable[tuple[bytes, int]], wake_word_id: str | None
    ) -> wake_word.DetectionResult | None:
        """Try to detect one or more wake words in an audio stream.

        Audio must be 16Khz sample rate with 16-bit mono PCM samples.
        """

        async def next_chunk():
            """Get the next chunk from audio stream."""
            async for chunk_bytes in stream:
                return chunk_bytes
            return None

        try:
            async with AsyncTcpClient(self.service.host, self.service.port) as client:
                # Inform client which wake word we want to detect (None = default)
                await client.write_event(
                    Detect(names=[wake_word_id] if wake_word_id else None).event()
                )

                await client.write_event(
                    AudioStart(
                        rate=16000,
                        width=2,
                        channels=1,
                    ).event(),
                )

                # Read audio and wake events in "parallel"
                audio_task = asyncio.create_task(next_chunk())
                wake_task = asyncio.create_task(client.read_event())
                pending = {audio_task, wake_task}

                try:
                    while True:
                        done, pending = await asyncio.wait(
                            pending, return_when=asyncio.FIRST_COMPLETED
                        )

                        if wake_task in done:
                            event = wake_task.result()
                            if event is None:
                                _LOGGER.debug("Connection lost")
                                break

                            if Error.is_type(event.type):
                                _LOGGER.error(
                                    error_event_message(Error.from_event(event))
                                )
                                break

                            if Detection.is_type(event.type):
                                # Possible detection
                                detection = Detection.from_event(event)
                                _LOGGER.info(detection)

                                if wake_word_id and (detection.name != wake_word_id):
                                    _LOGGER.warning(
                                        "Expected wake word %s but got %s, skipping",
                                        wake_word_id,
                                        detection.name,
                                    )
                                    wake_task = asyncio.create_task(client.read_event())
                                    pending.add(wake_task)
                                    continue

                                # Retrieve queued audio
                                queued_audio: list[tuple[bytes, int]] | None = None
                                if audio_task in pending:
                                    # Save queued audio
                                    await audio_task
                                    pending.remove(audio_task)
                                    queued_audio = [audio_task.result()]

                                return wake_word.DetectionResult(
                                    wake_word_id=detection.name or "",
                                    wake_word_phrase=self._get_phrase(
                                        detection.name or ""
                                    ),
                                    timestamp=detection.timestamp,
                                    queued_audio=queued_audio,
                                )

                            # Next event
                            wake_task = asyncio.create_task(client.read_event())
                            pending.add(wake_task)

                        if audio_task in done:
                            # Forward audio to wake service
                            chunk_info = audio_task.result()
                            if chunk_info is None:
                                break

                            chunk_bytes, chunk_timestamp = chunk_info
                            chunk = AudioChunk(
                                rate=16000,
                                width=2,
                                channels=1,
                                audio=chunk_bytes,
                                timestamp=chunk_timestamp,
                            )
                            await client.write_event(chunk.event())

                            # Next chunk
                            audio_task = asyncio.create_task(next_chunk())
                            pending.add(audio_task)
                finally:
                    # Clean up
                    if audio_task in pending:
                        # It's critical that we don't cancel the audio task or
                        # leave it hanging. This would mess up the pipeline STT
                        # by stopping the audio stream.
                        await audio_task
                        pending.remove(audio_task)

                    for task in pending:
                        task.cancel()

        except OSError, WyomingError:
            _LOGGER.exception("Error processing audio stream")

        return None

    def _get_phrase(self, model_id: str) -> str:
        """Get wake word phrase for model id."""
        for ww_model in self._supported_wake_words:
            if not ww_model.phrase:
                continue

            if ww_model.id == model_id:
                return ww_model.phrase

        return model_id
