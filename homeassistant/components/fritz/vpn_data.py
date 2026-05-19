"""WireGuard VPN runtime storage (separate from AvmWrapper runtime_data)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .vpn_coordinator import FritzVpnCoordinator

_LOGGER = logging.getLogger(__name__)

FRITZ_VPN_DATA_KEY: HassKey[dict[str, FritzVpnEntryData]] = HassKey(f"{DOMAIN}_vpn")


@dataclass
class FritzVpnEntryData:
    """Per-entry WireGuard VPN state."""

    coordinator: FritzVpnCoordinator
    known_uids: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def vpn_entry_data(hass: HomeAssistant, entry_id: str) -> FritzVpnEntryData | None:
    """Return VPN runtime data for a config entry, if loaded."""
    return hass.data.get(FRITZ_VPN_DATA_KEY, {}).get(entry_id)


async def async_setup_vpn(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Start WireGuard VPN coordinator for a FRITZ!Box Tools config entry."""
    vpn_coordinator = FritzVpnCoordinator(
        hass,
        dict(entry.data),
        entry_id=entry.entry_id,
    )
    try:
        await vpn_coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning(
            "WireGuard VPN setup failed for %s (integration continues): %s",
            entry.data.get(CONF_HOST, entry.title),
            err,
        )
        await vpn_coordinator.async_close()
        return

    hass.data.setdefault(FRITZ_VPN_DATA_KEY, {})[entry.entry_id] = FritzVpnEntryData(
        coordinator=vpn_coordinator
    )
    _LOGGER.debug(
        "WireGuard VPN: %d connection(s) for %s",
        len(vpn_coordinator.data or {}),
        entry.title,
    )


async def async_unload_vpn(hass: HomeAssistant, entry_id: str) -> None:
    """Stop WireGuard VPN coordinator for a config entry."""
    store = hass.data.get(FRITZ_VPN_DATA_KEY)
    if not store:
        return
    entry_data = store.pop(entry_id, None)
    if entry_data is None:
        return
    await entry_data.coordinator.async_close()
    if not store:
        hass.data.pop(FRITZ_VPN_DATA_KEY)
