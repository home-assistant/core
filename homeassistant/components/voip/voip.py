import asyncio
import functools
import logging
import socket
import time
import wave
from pathlib import Path

from homeassistant.core import HomeAssistant

from .sip import SipDatagramProtocol, CallInfo
from .rtp_audio import RtpOpusOutput

_LOGGER = logging.getLogger(__name__)


class VoipDatagramProtocol(SipDatagramProtocol):
    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__()
        self.hass = hass

    def on_call(self, call_info: CallInfo):
        """Callback for incoming call."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        # Bind to a random UDP port
        sock.bind((call_info.server_ip, 0))
        rtp_ip, rtp_port = sock.getsockname()
        _LOGGER.debug(
            "Starting RTP server on ip=%s, port=%s",
            rtp_ip,
            rtp_port,
        )

        self.hass.async_create_task(
            self.hass.loop.create_datagram_endpoint(
                lambda: MediaOutputDatagramProtocol(
                    self.hass,
                    "/home/hansenm/opt/homeassistant/config/media/apope_lincoln.wav",
                    silence_before=0.5,
                ),
                (rtp_ip, rtp_port),
            )
        )

        self.answer(call_info, rtp_port)


class MediaOutputDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        hass: HomeAssistant,
        wav_path: str | Path,
        silence_before: float = 0.0,
    ) -> None:
        self.hass = hass
        self.transport = None
        self.silence_before = silence_before
        self.wav_path = str(wav_path)
        self._rtp_output = RtpOpusOutput()
        self._media_sent = False

    def connection_made(self, transport):
        self.transport = transport
        _LOGGER.debug(
            "Started UDP server on %s",
            self.transport.get_extra_info("sockname"),
        )

    def datagram_received(self, data, addr):
        # Send media when first packet is received from caller
        if self._media_sent:
            return

        self._media_sent = True
        self.hass.async_add_executor_job(
            functools.partial(
                self._send_media,
                addr,
            )
        )

    def _send_media(self, addr):
        assert self.transport is not None

        # Pause before sending to allow time for user to pick up phone.
        time.sleep(self.silence_before)

        wav_file: wave.Wave_read = wave.open(self.wav_path, "rb")
        with wav_file:
            rate = wav_file.getframerate()
            width = wav_file.getsampwidth()
            channels = wav_file.getnchannels()
            frames_left = wav_file.getnframes()
            seconds_per_rtp = (
                self._rtp_output.opus_frame_size / self._rtp_output.opus_rate
            )

            while chunk := wav_file.readframes(self._rtp_output.opus_frame_size):
                frames_left -= len(chunk)
                for rtp_bytes in self._rtp_output.process_audio(
                    chunk,
                    rate,
                    width,
                    channels,
                    is_end=frames_left > 0,
                ):
                    # _LOGGER.debug(len(rtp_bytes))
                    self.transport.sendto(rtp_bytes, addr)

                    # Wait almost the full amount of time for the chunk.
                    #
                    # Sending too fast will cause the phone to skip chunks,
                    # since it doesn't seem to have a very large buffer.
                    #
                    # Sending too slow will cause audio artifacts if there is
                    # network jitter, which is why programs like GStreamer are
                    # much better at this.
                    time.sleep(seconds_per_rtp * 0.95)

        # Done
        self.transport.close()
        self.transport = None
