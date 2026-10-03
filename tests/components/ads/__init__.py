"""Tests for the ADS integration."""

import ctypes
from typing import Any

import pyads

from homeassistant.components.ads.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import AMS_NET_ID, IP_ADDRESS, PORT

ADS_CONFIG = {"device": AMS_NET_ID, "ip_address": IP_ADDRESS, "port": PORT}


async def setup_ads_platform(
    hass: HomeAssistant, platform: str, platform_config: Any
) -> bool:
    """Set up the ADS connection and one of its entity platforms from YAML."""
    return await async_setup_component(
        hass, platform, {DOMAIN: ADS_CONFIG, platform: platform_config}
    )


def build_notification(handle: int, payload: bytes) -> Any:
    """Build the notification struct the ADS router hands to a callback."""
    header = pyads.structs.SAdsNotificationHeader
    buffer = (ctypes.c_ubyte * (header.data.offset + len(payload)))()
    notification = ctypes.cast(buffer, ctypes.POINTER(header))
    notification.contents.hNotification = handle
    notification.contents.cbSampleSize = len(payload)
    ctypes.memmove(ctypes.addressof(buffer) + header.data.offset, payload, len(payload))
    return notification
