"""The Mikrotik component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry

from .const import (
    ATTR_MANUFACTURER,
    CLIENTS,
    CONF_ARP_PING,
    CONF_DHCP_SERVER_TRACK_MODE,
    DOMAIN,
    PLATFORMS,
)
from .hub import MikrotikHub


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Mikrotik component."""

    hub = MikrotikHub(hass, config_entry)

    await hub.async_setup()

    hass.config_entries.async_update_entry(
        config_entry,
        title=f"{hub.hub_data.hostname} ({hub.host})",
        unique_id=config_entry.data[CONF_HOST],
    )
    if CONF_ARP_PING in config_entry.options:
        dhcp_track_mode = (
            "ARP ping" if config_entry.options[CONF_ARP_PING] else "DHCP lease"
        )

        hass.config_entries.async_update_entry(
            config_entry,
            options={
                **config_entry.options,
                CONF_DHCP_SERVER_TRACK_MODE: dhcp_track_mode,
            },
        )

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = hub
    hass.data[DOMAIN].setdefault(CLIENTS, {})
    await hub.async_refresh()
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    device_registry: DeviceRegistry = hass.helpers.device_registry.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, hub.host)},
        default_manufacturer=ATTR_MANUFACTURER,
        default_model=hub.hub_data.model,
        default_name=hub.hub_data.hostname,
        sw_version=hub.hub_data.firmware,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DOMAIN].pop(config_entry.entry_id)
    # if only CLIENTS key is there del the DOMAIN key
    if len(hass.data[DOMAIN]) == 1:
        del hass.data[DOMAIN]

    return unload_ok
