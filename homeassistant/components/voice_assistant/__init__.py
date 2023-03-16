"""The Voice Assistant integration."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_PIPELINE, DOMAIN
from .pipeline import Pipeline
from .websocket_api import async_register_websocket_api

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Voice Assistant integration."""
    hass.data[DOMAIN] = {
        DEFAULT_PIPELINE: Pipeline(
            name=DEFAULT_PIPELINE,
            language=hass.config.language,
            stt_engine="cloud",
            agent_id="homeassistant",
            tts_engine="cloud",
        )
    }
    async_register_websocket_api(hass)

    return True
