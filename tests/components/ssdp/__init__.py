"""Tests for the SSDP integration."""

from __future__ import annotations

from datetime import datetime

from async_upnp_client.ssdp import udn_from_headers
from async_upnp_client.ssdp_listener import SsdpListener
from async_upnp_client.utils import CaseInsensitiveDict

from homeassistant.components import ssdp
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def init_ssdp_component(hass: HomeAssistant) -> SsdpListener:
    """Initialize ssdp component and get SsdpListener."""
    await async_setup_component(hass, ssdp.DOMAIN, {ssdp.DOMAIN: {}})
    await hass.async_block_till_done()
    return hass.data[ssdp.DOMAIN][ssdp.SSDP_SCANNER]._ssdp_listeners[0]


def _ssdp_headers(headers) -> CaseInsensitiveDict:
    """Create a CaseInsensitiveDict with headers and a timestamp."""
    ssdp_headers = CaseInsensitiveDict(headers, _timestamp=datetime.now())
    ssdp_headers["_udn"] = udn_from_headers(ssdp_headers)
    return ssdp_headers
