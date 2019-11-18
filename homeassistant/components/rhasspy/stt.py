"""
Support for Rhasspy speech to text.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
import logging
from typing import List

import aiohttp
from rhasspyclient import RhasspyClient
import voluptuous as vol

from homeassistant.components.stt import Provider, SpeechMetadata, SpeechResult
from homeassistant.components.stt.const import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechResultState,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import SUPPORT_LANGUAGES

# -----------------------------------------------------------------------------

_LOGGER = logging.getLogger(__name__)

# Base URL of Rhasspy web API
CONF_API_URL = "api_url"

# Default settings
DEFAULT_API_URL = "http://localhost:12101/api/"

# Config
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({vol.Optional(CONF_API_URL): cv.url})

# -----------------------------------------------------------------------------


async def async_get_engine(hass, config, discovery_info):
    """Set up Rhasspy speech to text component."""
    provider = RhasspySTTProvider(hass, config)
    _LOGGER.debug("Loaded Rhasspy stt provider")

    # Register WAV speech to text test endpoint

    return provider


# -----------------------------------------------------------------------------


class RhasspySTTProvider(Provider):
    """Rhasspy speech to text provider."""

    def __init__(self, hass, conf):
        """Create Rhasspy speech to text provider."""
        self.hass = hass
        self.config = conf

        # URL to stream microphone audio
        self.api_url = conf.get(CONF_API_URL, DEFAULT_API_URL)

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: aiohttp.StreamReader
    ) -> SpeechResult:
        """Process an audio stream to STT service.

        Only streaming of content are allow!
        """
        _LOGGER.debug("Receiving audio")
        try:
            # Drop WAV header
            await stream.readchunk()

            # Stream to Rhasspy server
            session = async_get_clientsession(self.hass)
            client = RhasspyClient(self.api_url, session)
            text = await client.stream_to_text(stream)

            return SpeechResult(text=text, result=SpeechResultState.SUCCESS)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("async_process_audio_stream")

        return SpeechResult(text="", result=SpeechResultState.ERROR)

    # -------------------------------------------------------------------------

    @property
    def supported_languages(self) -> List[str]:
        """Return a list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_formats(self) -> List[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> List[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> List[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> List[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> List[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]
