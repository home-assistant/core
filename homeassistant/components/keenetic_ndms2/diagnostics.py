"""Diagnostics support for Keenetic NDMS2 Router."""

from collections import Counter
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONSIDER_HOME,
    CONF_INCLUDE_ARP,
    CONF_INCLUDE_ASSOCIATED,
    CONF_INTERFACES,
    CONF_TRY_HOTSPOT,
)
from .router import KeeneticConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KeeneticConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    router = entry.runtime_data
    router_info = router.router_info
    if TYPE_CHECKING:
        # Setup fails when the router information can't be fetched
        assert router_info is not None
    clients = list(router.last_devices.values())

    # The host, credentials, router name, and region are left out, as are the
    # MAC addresses, IP addresses, and names of the clients. Clients are only
    # counted per tracked interface.
    return {
        "config_entry": {
            CONF_INTERFACES: entry.options[CONF_INTERFACES],
            CONF_CONSIDER_HOME: entry.options[CONF_CONSIDER_HOME],
            CONF_TRY_HOTSPOT: entry.options[CONF_TRY_HOTSPOT],
            CONF_INCLUDE_ARP: entry.options[CONF_INCLUDE_ARP],
            CONF_INCLUDE_ASSOCIATED: entry.options[CONF_INCLUDE_ASSOCIATED],
        },
        "router": {
            "available": router.available,
            "model": router_info.model,
            "manufacturer": router_info.manufacturer,
            "vendor": router_info.vendor,
            "hw_version": router_info.hw_version,
            "fw_version": router_info.fw_version,
            "fw_channel": router_info.fw_channel,
        },
        "clients": {
            "total": len(clients),
            "per_interface": dict(
                sorted(Counter(client.interface for client in clients).items())
            ),
        },
    }
