"""Pipeline tests for Voice Assistant integration."""
from collections.abc import AsyncIterable
from unittest.mock import MagicMock, patch

import pytest




# @pytest.fixture(autouse=True)
# async def init_components(hass):
#     """Initialize relevant components with empty configs."""
#     assert await async_setup_component(hass, "media_source", {})
#     assert await async_setup_component(
#         hass,
#         "tts",
#         {
#             "tts": {
#                 "platform": "demo",
#             }
#         },
#     )
#     assert await async_setup_component(hass, "stt", {})

#     # mock_platform fails because it can't import
#     hass.data[stt.DOMAIN] = {"test": MockSttProvider()}

#     assert await async_setup_component(hass, "voice_assistant", {})

#     with patch(
#         "homeassistant.components.demo.tts.DemoProvider.get_tts_audio",
#         return_value=("mp3", b""),
#     ) as mock_get_tts:
#         yield mock_get_tts


# @pytest.fixture
# async def stt_metadata(hass):
#     return stt.SpeechMetadata(
#         language=hass.config.language,
#         format=stt.AudioFormats.WAV,
#         codec=stt.AudioCodecs.PCM,
#         bit_rate=stt.AudioBitRates.BITRATE_16,
#         sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
#         channel=stt.AudioChannels.CHANNEL_MONO,
#     )


# async def test_audio_pipeline(hass, stt_metadata):
#     """Run audio pipeline with mock TTS."""
#     pipeline = Pipeline(
#         name="test",
#         language=hass.config.language,
#         stt_engine=None,
#         conversation_engine=None,
#         tts_engine=None,
#     )

#     async def stt_stream():
#         while True:
#             yield bytes(1)

#     event_callback = MagicMock()
#     await AudioPipelineRequest(stt_metadata, stt_stream()).execute(
#         PipelineRun(
#             hass,
#             context=Context(),
#             pipeline=pipeline,
#             event_callback=event_callback,
#             language=hass.config.language,
#         )
#     )

#     calls = event_callback.mock_calls
#     assert calls[0].args[0].type == PipelineEventType.RUN_START
#     assert calls[0].args[0].data == {
#         "pipeline": "test",
#         "language": hass.config.language,
#     }

#     # Speech to text
#     assert calls[1].args[0].type == PipelineEventType.STT_START
#     assert calls[1].args[0].data == {
#         "engine": "default",
#     }
#     assert calls[2].args[0].type == PipelineEventType.STT_FINISH

#     # Intent recognition
#     assert calls[3].args[0].type == PipelineEventType.INTENT_START
#     assert calls[3].args[0].data == {
#         "engine": "default",
#         "intent_input": "test stt transcript",
#     }
#     assert calls[4].args[0].type == PipelineEventType.INTENT_FINISH
#     assert calls[4].args[0].data == {
#         "intent_output": {
#             "conversation_id": None,
#             "response": {
#                 "card": {},
#                 "data": {"code": "no_intent_match"},
#                 "language": hass.config.language,
#                 "response_type": "error",
#                 "speech": {
#                     "plain": {
#                         "extra_data": None,
#                         "speech": "Sorry, I couldn't understand that",
#                     }
#                 },
#             },
#         }
#     }

#     # Text to speech
#     assert calls[5].args[0].type == PipelineEventType.TTS_START
#     assert calls[5].args[0].data == {
#         "engine": "default",
#         "tts_input": "Sorry, I couldn't understand that",
#     }
#     assert calls[6].args[0].type == PipelineEventType.TTS_FINISH
#     assert (
#         calls[6].args[0].data["tts_output"]
#         == f"/api/tts_proxy/dae2cdcb27a1d1c3b07ba2c7db91480f9d4bfd8f_{hass.config.language}_-_demo.mp3"
#     )

#     assert calls[7].args[0].type == PipelineEventType.RUN_FINISH


# async def test_stt_provider_missing(hass, stt_metadata):
#     """Run audio pipeline with missing STT provider."""
#     pipeline = Pipeline(
#         name="test",
#         language=hass.config.language,
#         stt_engine="does-not-exist",
#         conversation_engine=None,
#         tts_engine=None,
#     )

#     async def stt_stream():
#         while True:
#             yield bytes(1)

#     event_callback = MagicMock()
#     await AudioPipelineRequest(stt_metadata, stt_stream()).execute(
#         PipelineRun(
#             hass,
#             context=Context(),
#             pipeline=pipeline,
#             event_callback=event_callback,
#             language=hass.config.language,
#         )
#     )
