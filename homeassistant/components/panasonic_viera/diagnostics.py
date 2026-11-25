"""Diagnostics support for Panasonic Viera."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from . import PanasonicVieraConfigEntry
from .const import ATTR_UDN, CONF_APP_ID, CONF_ENCRYPTION_KEY, CONF_ON_ACTION

# The UPnP identifiers of a TV all embed its MAC address, and the turn-on
# action may carry credentials, such as a SecureOn password
TO_REDACT = {
    CONF_HOST,
    CONF_MAC,
    CONF_UNIQUE_ID,
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    CONF_ON_ACTION,
    ATTR_UDN,
    "viera:X_DMSUDN",
    "viera:X_DMRUDN",
    "viera:X_NRCUDN",
    "viera:X_PACUDN",
    "viera:X_NRC_ID",
    "vli:X_MHC_DEVICE_ID",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PanasonicVieraConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    remote = entry.runtime_data
    # The state as reported by the entities, which the fetch below leaves alone
    remote_data = {
        "state": remote.state,
        "available": remote.available,
        "volume": remote.volume,
        "muted": remote.muted,
        "playing": remote.playing,
        "source_list": remote.source_list,
        "source": remote.source,
    }
    # The description served by the TV now, None when it is unreachable
    device_info = await remote.async_fetch_device_info()

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "remote": remote_data,
            "device_info": device_info,
        },
        TO_REDACT,
    )
