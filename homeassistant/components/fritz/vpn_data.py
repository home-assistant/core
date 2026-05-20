"""WireGuard VPN runtime storage (separate from AvmWrapper runtime_data)."""

import asyncio
from dataclasses import dataclass, field
import logging

from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FRITZ_VPN_DATA_KEY: HassKey[dict[str, "FritzVpnEntryData"]] = HassKey(f"{DOMAIN}_vpn")


@dataclass
class FritzVpnEntryData:
    """Runtime data for WireGuard VPN on a FRITZ!Box Tools config entry."""

    known_uids: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def vpn_entry_data(hass: HomeAssistant, entry_id: str) -> FritzVpnEntryData | None:
    """Return VPN runtime data for a config entry, if present."""
    return hass.data.get(FRITZ_VPN_DATA_KEY, {}).get(entry_id)


async def async_setup_vpn(hass: HomeAssistant, entry_id: str) -> None:
    """Set up the WireGuard VPN data storage for a config entry.

    Note: VPN data fetching is now integrated into AvmWrapper._async_update_data().
    This function only initializes the per-entry tracking data (known_uids).
    """
    hass.data.setdefault(FRITZ_VPN_DATA_KEY, {})[entry_id] = FritzVpnEntryData()


async def async_unload_vpn(hass: HomeAssistant, entry_id: str) -> None:
    """Tear down WireGuard VPN data storage for a config entry."""
    store = hass.data.get(FRITZ_VPN_DATA_KEY)
    if not store:
        return
    store.pop(entry_id, None)
    if not store:
        hass.data.pop(FRITZ_VPN_DATA_KEY)
