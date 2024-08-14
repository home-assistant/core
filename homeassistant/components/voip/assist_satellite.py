"""Assist satellite entity for VoIP integration."""

from __future__ import annotations

from collections.abc import AsyncIterable
import logging
import time
from typing import TYPE_CHECKING, Final
from uuid import uuid4

from homeassistant.components import stt
from homeassistant.components.assist_pipeline import (
    PipelineEvent,
    PipelineEventCallback,
    PipelineEventType,
    PipelineStage,
    async_pipeline_from_audio_stream,
)
from homeassistant.components.assist_satellite import (
    AssistSatelliteEntity,
    AssistSatelliteEntityFeature,
    AssistSatelliteState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .devices import VoIPDevice
from .entity import VoIPEntity

if TYPE_CHECKING:
    from . import DomainData

_LOGGER = logging.getLogger(__name__)

_CONVERSATION_TIMEOUT_SEC: Final = 5 * 60  # 5 minutes


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up VoIP Assist satellite entity."""
    domain_data: DomainData = hass.data[DOMAIN]

    @callback
    def async_add_device(device: VoIPDevice) -> None:
        """Add device."""
        async_add_entities([VoipAssistSatellite(hass, device)])

    domain_data.devices.async_add_new_device_listener(async_add_device)

    entities: list[VoIPEntity] = [
        VoipAssistSatellite(hass, device) for device in domain_data.devices
    ]

    async_add_entities(entities)


class VoipAssistSatellite(VoIPEntity, AssistSatelliteEntity):
    """Assist satellite for VoIP devices."""

    def __init__(self, hass: HomeAssistant, voip_device: VoIPDevice) -> None:
        """Initialize an Assist satellite."""
        VoIPEntity.__init__(self, voip_device)
        AssistSatelliteEntity.__init__(self)

        # Conversation id is reset after 5 minutes of inactivity
        self._conversation_id: str | None = None
        self._conversation_id_time: float | None = None

        self._satellite_state: AssistSatelliteState = AssistSatelliteState.IDLE

    @property
    def state(self) -> AssistSatelliteState:
        """Return the current state of the satellite."""
        return self._satellite_state

    @property
    def supported_features(self) -> AssistSatelliteEntityFeature:
        """Return supported features of the satellite."""
        return (
            AssistSatelliteEntityFeature.AUDIO_INPUT
            | AssistSatelliteEntityFeature.AUDIO_OUTPUT
        )

    async def _async_accept_pipeline_from_satellite(
        self,
        context: Context,
        event_callback: PipelineEventCallback,
        audio_stream: AsyncIterable[bytes],
        start_stage: PipelineStage = PipelineStage.STT,
        end_stage: PipelineStage = PipelineStage.TTS,
        wake_word_phrase: str | None = None,
    ) -> None:
        """Triggers an Assist pipeline in Home Assistant from a satellite."""

        # Reset conversation id, if necessary
        if (self._conversation_id_time is None) or (
            (time.monotonic() - self._conversation_id_time) > _CONVERSATION_TIMEOUT_SEC
        ):
            self._conversation_id = None

        if self._conversation_id is None:
            self._conversation_id = str(uuid4())

        # Update timeout
        self._conversation_id_time = time.monotonic()

        # Set entity state based on pipeline events
        has_tts = False
        self._set_state(AssistSatelliteState.LISTENING)

        def _event_callback(event: PipelineEvent) -> None:
            nonlocal has_tts
            if event.type == PipelineEventType.STT_END:
                self._set_state(AssistSatelliteState.PROCESSING)
            elif event.type == PipelineEventType.TTS_END:
                # Wait until response_finished is called to return to idle
                has_tts = True
                self._set_state(AssistSatelliteState.RESPONDING)
            elif event.type == PipelineEventType.RUN_END:
                if not has_tts:
                    self._set_state(AssistSatelliteState.IDLE)

            event_callback(event)

        await async_pipeline_from_audio_stream(
            self.hass,
            context=context,
            event_callback=_event_callback,
            stt_metadata=stt.SpeechMetadata(
                language="",  # set in async_pipeline_from_audio_stream
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=audio_stream,
            pipeline_id=self.satellite_config.default_pipeline,
            conversation_id=self._conversation_id,
            device_id=self.voip_device.device_id,
            tts_audio_output="wav",
        )

    def response_finished(self) -> None:
        """Tell entity that the text-to-speech response has finished playing."""
        self._set_state(AssistSatelliteState.IDLE)

    def _set_state(self, state: AssistSatelliteState):
        """Set the entity's state."""
        self._satellite_state = state
        self.async_write_ha_state()

    async def _async_config_updated(self) -> None:
        """Inform when the device config is updated.

        Platforms need to make sure that the device has this configuration.
        """

    async def async_set_microphone_mute(self, mute: bool) -> None:
        """Mute or unmute the satellite's microphone."""
