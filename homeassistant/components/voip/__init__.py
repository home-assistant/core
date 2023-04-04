"""The Voice over IP integration."""
from __future__ import annotations

import logging

from homeassistant.components import media_source
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .pipeline import PipelineDatagramProtocol
from .sip import SIP_PORT

_LOGGER = logging.getLogger(__name__)
_IP_WILDCARD = "0.0.0.0"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    x = await media_source.async_resolve_media(
        hass, "media-source://media_source/local/apope_lincoln.wav"
    )
    _LOGGER.info(x.url)

    hass.async_create_background_task(
        hass.loop.create_datagram_endpoint(
            lambda: PipelineDatagramProtocol(hass),
            local_addr=(_IP_WILDCARD, SIP_PORT),
        ),
        "voip_sip",
    )

    return True
