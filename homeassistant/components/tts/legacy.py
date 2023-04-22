"""Provide the legacy TTS service provider interface."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Coroutine, Mapping
from functools import partial
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
import yarl

from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DESCRIPTION,
    CONF_NAME,
    CONF_PLATFORM,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_per_platform, discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_prepare_setup_platform
from homeassistant.util.network import normalize_url
from homeassistant.util.yaml import load_yaml

from .const import (
    ATTR_CACHE,
    ATTR_LANGUAGE,
    ATTR_MESSAGE,
    ATTR_OPTIONS,
    CONF_BASE_URL,
    CONF_CACHE,
    CONF_CACHE_DIR,
    CONF_FIELDS,
    CONF_TIME_MEMORY,
    DATA_TTS_MANAGER,
    DEFAULT_CACHE,
    DEFAULT_CACHE_DIR,
    DEFAULT_TIME_MEMORY,
    DOMAIN,
    TtsAudioType,
)
from .media_source import generate_media_source_id
from .models import Voice

if TYPE_CHECKING:
    from . import SpeechManager

_LOGGER = logging.getLogger(__name__)

CONF_SERVICE_NAME = "service_name"


def _deprecated_platform(value: str) -> str:
    """Validate if platform is deprecated."""
    if value == "google":
        raise vol.Invalid(
            "google tts service has been renamed to google_translate,"
            " please update your configuration."
        )
    return value


def _valid_base_url(value: str) -> str:
    """Validate base url, return value."""
    url = yarl.URL(cv.url(value))

    if url.path != "/":
        raise vol.Invalid("Path should be empty")

    return normalize_url(value)


PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): vol.All(cv.string, _deprecated_platform),
        vol.Optional(CONF_CACHE, default=DEFAULT_CACHE): cv.boolean,
        vol.Optional(CONF_CACHE_DIR, default=DEFAULT_CACHE_DIR): cv.string,
        vol.Optional(CONF_TIME_MEMORY, default=DEFAULT_TIME_MEMORY): vol.All(
            vol.Coerce(int), vol.Range(min=60, max=57600)
        ),
        vol.Optional(CONF_BASE_URL): _valid_base_url,
        vol.Optional(CONF_SERVICE_NAME): cv.string,
    }
)
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE.extend(PLATFORM_SCHEMA.schema)

SERVICE_SAY = "say"

SCHEMA_SERVICE_SAY = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_CACHE): cv.boolean,
        vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
        vol.Optional(ATTR_LANGUAGE): cv.string,
        vol.Optional(ATTR_OPTIONS): dict,
    }
)


async def async_setup_legacy(
    hass: HomeAssistant, config: ConfigType
) -> list[Coroutine[Any, Any, None]]:
    """Set up legacy text to speech providers."""
    tts: SpeechManager = hass.data[DATA_TTS_MANAGER]

    # Load service descriptions from tts/services.yaml
    services_yaml = Path(__file__).parent / "services.yaml"
    services_dict = cast(
        dict, await hass.async_add_executor_job(load_yaml, str(services_yaml))
    )

    async def async_setup_platform(
        p_type: str,
        p_config: ConfigType | None = None,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up a TTS platform."""
        if p_config is None:
            p_config = {}

        platform = await async_prepare_setup_platform(hass, config, DOMAIN, p_type)
        if platform is None:
            _LOGGER.error("Unknown text to speech platform specified")
            return

        try:
            if hasattr(platform, "async_get_engine"):
                provider = await platform.async_get_engine(
                    hass, p_config, discovery_info
                )
            else:
                provider = await hass.async_add_executor_job(
                    platform.get_engine, hass, p_config, discovery_info
                )

            if provider is None:
                _LOGGER.error("Error setting up platform: %s", p_type)
                return

            tts.async_register_legacy_engine(p_type, provider, p_config)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error setting up platform: %s", p_type)
            return

        async def async_say_handle(service: ServiceCall) -> None:
            """Service handle for say."""
            entity_ids = service.data[ATTR_ENTITY_ID]

            await hass.services.async_call(
                DOMAIN_MP,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: entity_ids,
                    ATTR_MEDIA_CONTENT_ID: generate_media_source_id(
                        hass,
                        engine=p_type,
                        message=service.data[ATTR_MESSAGE],
                        language=service.data.get(ATTR_LANGUAGE),
                        options=service.data.get(ATTR_OPTIONS),
                        cache=service.data.get(ATTR_CACHE),
                    ),
                    ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                    ATTR_MEDIA_ANNOUNCE: True,
                },
                blocking=True,
                context=service.context,
            )

        service_name = p_config.get(CONF_SERVICE_NAME, f"{p_type}_{SERVICE_SAY}")
        hass.services.async_register(
            DOMAIN, service_name, async_say_handle, schema=SCHEMA_SERVICE_SAY
        )

        # Register the service description
        service_desc = {
            CONF_NAME: f"Say a TTS message with {p_type}",
            CONF_DESCRIPTION: (
                f"Say something using text-to-speech on a media player with {p_type}."
            ),
            CONF_FIELDS: services_dict[SERVICE_SAY][CONF_FIELDS],
        }
        async_set_service_schema(hass, DOMAIN, service_name, service_desc)

    async def async_platform_discovered(
        platform: str, info: dict[str, Any] | None
    ) -> None:
        """Handle for discovered platform."""
        await async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return [
        async_setup_platform(p_type, p_config)
        for p_type, p_config in config_per_platform(config, DOMAIN)
        if p_type is not None
    ]


class Provider:
    """Represent a single TTS provider."""

    hass: HomeAssistant | None = None
    name: str | None = None

    @property
    def default_language(self) -> str | None:
        """Return the default language."""
        return None

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""

    @property
    def supported_options(self) -> list[str] | None:
        """Return a list of supported options like voice, emotions."""
        return None

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return a list of supported voices for a language."""
        return None

    @property
    def default_options(self) -> Mapping[str, Any] | None:
        """Return a mapping with the default options."""
        return None

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Load tts audio file from provider."""
        raise NotImplementedError()

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Load tts audio file from provider.

        Return a tuple of file extension and data as bytes.
        """
        if TYPE_CHECKING:
            assert self.hass
        return await self.hass.async_add_executor_job(
            partial(self.get_tts_audio, message, language, options=options)
        )
