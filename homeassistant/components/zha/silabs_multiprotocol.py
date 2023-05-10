"""Silicon Labs Multiprotocol support."""

from __future__ import annotations

import contextlib

from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    is_multiprotocol_url,
)
from homeassistant.core import HomeAssistant

from . import api


def _get_zha_url(hass: HomeAssistant) -> str | None:
    """Return the ZHA radio path, or None if there's no ZHA config entry."""
    with contextlib.suppress(ValueError):
        return api.async_get_radio_path(hass)
    return None


async def _get_zha_channel(hass: HomeAssistant) -> int | None:
    """Get ZHA channel, or None if there's no ZHA config entry."""
    zha_network_settings: api.NetworkBackup | None
    with contextlib.suppress(ValueError):
        zha_network_settings = await api.async_get_network_settings(hass)
    if not zha_network_settings:
        return None
    channel: int = zha_network_settings.network_info.channel
    # ZHA uses channel 0 when no channel is set
    return channel or None


async def async_change_channel(hass: HomeAssistant, channel: int) -> None:
    """Set the channel to be used.

    Does nothing if not configured.
    """
    zha_url = _get_zha_url(hass)
    if not zha_url:
        # ZHA is not configured
        return None

    return await api.async_change_channel(hass, channel)


async def async_get_channel(hass: HomeAssistant) -> int | None:
    """Return the channel.

    Returns None if not configured.
    """
    zha_url = _get_zha_url(hass)
    if not zha_url:
        # ZHA is not configured
        return None

    return await _get_zha_channel(hass)


async def async_using_multipan(hass: HomeAssistant) -> bool:
    """Return if the multiprotocol device is used.

    Returns False if not configured.
    """
    zha_url = _get_zha_url(hass)
    if not zha_url:
        # ZHA is not configured
        return False

    return is_multiprotocol_url(zha_url)
