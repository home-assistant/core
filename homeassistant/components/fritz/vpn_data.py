"""WireGuard VPN runtime storage (separate from AvmWrapper runtime_data)."""

import asyncio
from dataclasses import dataclass, field
import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .vpn_coordinator import (
    FritzVpnCoordinator,
    async_start_entry_reauth,
    vpn_auth_failed,
)

_LOGGER = logging.getLogger(__name__)

FRITZ_VPN_DATA_KEY: HassKey[dict[str, FritzVpnEntryData]] = HassKey(f"{DOMAIN}_vpn")


@dataclass
class FritzVpnEntryData:
    """Runtime data for WireGuard VPN on a FRITZ!Box Tools config entry."""

    coordinator: FritzVpnCoordinator
    known_uids: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def vpn_entry_data(hass: HomeAssistant, entry_id: str) -> FritzVpnEntryData | None:
    """Return VPN runtime data for a config entry, if present."""
    return hass.data.get(FRITZ_VPN_DATA_KEY, {}).get(entry_id)


async def _reauth_after_setup(hass: HomeAssistant, entry_id: str) -> None:
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.state != ConfigEntryState.LOADED:
        return
    await async_start_entry_reauth(hass, entry)


async def async_setup_vpn(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the WireGuard VPN coordinator for a config entry."""
    coordinator = FritzVpnCoordinator(
        hass,
        dict(entry.data),
        entry_id=entry.entry_id,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except (UpdateFailed, ConnectionError, ValueError, TimeoutError, OSError) as err:
        _LOGGER.warning(
            "WireGuard VPN setup failed for %s (integration continues): %s",
            entry.data.get(CONF_HOST, entry.title),
            err,
        )
        await coordinator.async_close()
        if vpn_auth_failed(err):
            hass.async_create_task(_reauth_after_setup(hass, entry.entry_id))
        return
    except AttributeError as err:
        # Some underlying client/session issues can surface as AttributeError
        # (for example from an unusable socket resolver).
        # This must not block the core `fritz` integration from setting up.
        _LOGGER.warning(
            "WireGuard VPN setup failed for %s (integration continues): %s",
            entry.data.get(CONF_HOST, entry.title),
            err,
        )
        await coordinator.async_close()
        return

    hass.data.setdefault(FRITZ_VPN_DATA_KEY, {})[entry.entry_id] = FritzVpnEntryData(
        coordinator=coordinator
    )


async def async_unload_vpn(hass: HomeAssistant, entry_id: str) -> None:
    """Tear down WireGuard VPN for a config entry."""
    store = hass.data.get(FRITZ_VPN_DATA_KEY)
    if not store:
        return
    entry_data = store.pop(entry_id, None)
    if entry_data is None:
        return
    await entry_data.coordinator.async_close()
    if not store:
        hass.data.pop(FRITZ_VPN_DATA_KEY)
