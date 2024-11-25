"""Handle legacy speech-to-text platforms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterable, Coroutine
import logging
from typing import Any

from homeassistant.config import config_per_platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import (
    SetupPhases,
    async_prepare_setup_platform,
    async_start_setup,
)

from .const import (
    DATA_PROVIDERS,
    DOMAIN,
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
)
from .models import SpeechMetadata, SpeechResult

_LOGGER = logging.getLogger(__name__)


@callback
def async_default_provider(hass: HomeAssistant) -> str | None:
    """Return the domain of the default provider."""
    providers = hass.data[DATA_PROVIDERS]
    return next(iter(providers), None)


@callback
def async_get_provider(
    hass: HomeAssistant, domain: str | None = None
) -> Provider | None:
    """Return provider."""
    providers = hass.data[DATA_PROVIDERS]
    if domain:
        return providers.get(domain)

    provider = async_default_provider(hass)
    return providers[provider] if provider is not None else None


@callback
def async_setup_legacy(
    hass: HomeAssistant, config: ConfigType
) -> list[Coroutine[Any, Any, None]]:
    """Set up legacy speech-to-text providers."""
    providers = hass.data[DATA_PROVIDERS] = {}

    async def async_setup_platform(
        p_type: str,
        p_config: ConfigType | None = None,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up an STT platform."""
        if p_config is None:
            p_config = {}

        platform = await async_prepare_setup_platform(hass, config, DOMAIN, p_type)
        if platform is None:
            _LOGGER.error("Unknown speech-to-text platform specified")
            return

        try:
            with async_start_setup(
                hass,
                integration=p_type,
                group=str(id(p_config)),
                phase=SetupPhases.PLATFORM_SETUP,
            ):
                provider = await platform.async_get_engine(
                    hass, p_config, discovery_info
                )

                provider.name = p_type
                provider.hass = hass

                providers[provider.name] = provider
        except Exception:
            _LOGGER.exception("Error setting up platform: %s", p_type)
            return

    # Add discovery support
    async def async_platform_discovered(
        platform: str, info: DiscoveryInfoType | None
    ) -> None:
        """Handle for discovered platform."""
        await async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return [
        async_setup_platform(p_type, p_config)
        for p_type, p_config in config_per_platform(config, DOMAIN)
        if p_type
    ]


class Provider(ABC):
    """Represent a single STT provider."""

    hass: HomeAssistant | None = None
    name: str | None = None

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""

    @property
    @abstractmethod
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""

    @property
    @abstractmethod
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""

    @property
    @abstractmethod
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bit rates."""

    @property
    @abstractmethod
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""

    @property
    @abstractmethod
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""

    @abstractmethod
    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Process an audio stream to STT service.

        Only streaming of content are allow!
        """

    @callback
    def check_metadata(self, metadata: SpeechMetadata) -> bool:
        """Check if given metadata supported by this provider."""
        if (
            metadata.language not in self.supported_languages
            or metadata.format not in self.supported_formats
            or metadata.codec not in self.supported_codecs
            or metadata.bit_rate not in self.supported_bit_rates
            or metadata.sample_rate not in self.supported_sample_rates
            or metadata.channel not in self.supported_channels
        ):
            return False
        return True
