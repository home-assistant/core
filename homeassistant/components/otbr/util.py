"""Utility functions for the Open Thread Border Router integration."""
from __future__ import annotations

import contextlib

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    is_multiprotocol_url,
)
from homeassistant.components.zha import api as zha_api
from homeassistant.core import HomeAssistant


def _get_zha_url(hass: HomeAssistant) -> str | None:
    """Get ZHA radio path, or None if there's no ZHA config entry."""
    with contextlib.suppress(ValueError):
        return zha_api.async_get_radio_path(hass)
    return None


async def _get_zha_channel(hass: HomeAssistant) -> int | None:
    """Get ZHA channel, or None if there's no ZHA config entry."""
    zha_network_settings: zha_api.NetworkBackup | None
    with contextlib.suppress(ValueError):
        zha_network_settings = await zha_api.async_get_network_settings(hass)
    if not zha_network_settings:
        return None
    channel: int = zha_network_settings.network_info.channel
    # ZHA uses channel 0 when no channel is set
    return channel or None


async def get_allowed_channel(hass: HomeAssistant, otbr_url: str) -> int | None:
    """Return the allowed channel, or None if there's no restriction."""
    if not is_multiprotocol_url(otbr_url):
        # The OTBR is not sharing the radio, no restriction
        return None

    zha_url = _get_zha_url(hass)
    if not zha_url or not is_multiprotocol_url(zha_url):
        # ZHA is not configured or not sharing the radio with this OTBR, no restriction
        return None

    return await _get_zha_channel(hass)
