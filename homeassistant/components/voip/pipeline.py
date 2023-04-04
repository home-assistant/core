from dataclasses import dataclass
import logging
import socket

from .media_playback import MediaPlaybackDatagramProtocol
from .sip import CallInfo, SIPDatagramProtocol

_LOGGER = logging.getLogger(__name__)


@dataclass
class PhoneSettings:
    pipeline_name: str | None = None
    pipeline_language: str | None = None
    media_content_id: str | None = None

    def __post_init__(self):
        assert any(
            (
                self.pipeline_name,
                self.pipeline_language,
                self.media_content_id,
            )
        ), "Pipeline name/language or media id must be set"


# @dataclass
# class VoIPSession:
#     pipeline: Pipeline
#     audio_queue: "asyncio.Queue[bytes]" = field(default=asyncio.Queue)


class PipelineDatagramProtocol(SIPDatagramProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._settings: dict[str, PhoneSettings] = {
            "192.168.68.82": PhoneSettings(
                media_content_id="media-source://media_source/local/apope_lincoln.wav"
            ),
        }

        # ip -> session
        # self._sessions: dict[str, VoIPSession] = {}

    def on_call(self, call_info: CallInfo):
        try:
            # while not self.audio_queue.empty():
            #     self.audio_queue.get_nowait()
            #
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            # sock.bind((call_info.server_ip, 0))
            rtp_port = 5004
            sock.bind((call_info.server_ip, 5004))

            # rtp_ip, rtp_port = sock.getsockname()
            _LOGGER.debug(
                "Starting RTP server at ip=%s, port=%s", call_info.caller_ip, rtp_port
            )

            self.hass.async_create_background_task(
                self.hass.loop.create_datagram_endpoint(
                    lambda: MediaPlaybackDatagramProtocol(
                        self.hass,
                        "/home/hansenm/opt/homeassistant/config/media/apope_lincoln.wav",
                    ),
                    local_addr=(call_info.server_ip, rtp_port),
                ),
                "media_playback",
            )

            # self.hass.async_create_background_task(self.run_pipeline(), "rtp-pipeline")
            self.answer(
                headers=call_info.headers,
                caller_ip=call_info.caller_ip,
                caller_sip_port=call_info.caller_sip_port,
                server_ip=call_info.server_ip,
                server_rtp_port=rtp_port,
            )
        except Exception:
            _LOGGER.exception("on_call")

    # async def run_pipeline(self):
    #     language = self.hass.config.language
    #     pipeline = async_get_pipeline(self.hass, language=language)

    #     async def stt_stream():
    #         segmenter = VoiceCommandSegmenter()

    #         # Yield until we receive an empty chunk
    #         while chunk := await self.audio_queue.get():
    #             if not segmenter.process(chunk):
    #                 # Voice command is finished
    #                 break

    #             yield chunk

    #     stt_metadata = stt.SpeechMetadata(
    #         language="en-US",
    #         format=stt.AudioFormats.WAV,
    #         codec=stt.AudioCodecs.PCM,
    #         bit_rate=stt.AudioBitRates.BITRATE_16,
    #         sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
    #         channel=stt.AudioChannels.CHANNEL_MONO,
    #     )

    #     _LOGGER.info("Starting pipeline")
    #     await PipelineInput(
    #         stt_metadata=stt_metadata,
    #         stt_stream=stt_stream(),
    #     ).execute(
    #         PipelineRun(
    #             self.hass,
    #             context=Context(),
    #             pipeline=pipeline,
    #             start_stage=PipelineStage.STT,
    #             end_stage=PipelineStage.TTS,
    #             event_callback=lambda event: event,
    #         )
    #     )
