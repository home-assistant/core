"""The Voice over IP integration."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .sip import SIP_PORT
from .voip import VoipDatagramProtocol

_LOGGER = logging.getLogger(__name__)
_IP_WILDCARD = "0.0.0.0"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Run a UDP server to respond to SIP requests."""
    await hass.loop.create_datagram_endpoint(
        lambda: VoipDatagramProtocol(hass),
        local_addr=(_IP_WILDCARD, SIP_PORT),
    )

    return True
