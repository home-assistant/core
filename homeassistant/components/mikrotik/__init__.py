"""The Mikrotik component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry

from .const import ATTR_MANUFACTURER, CLIENTS, CONF_REPEATER_MODE, DOMAIN, PLATFORMS
from .hub import MikrotikHub


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Mikrotik component."""

    hub = MikrotikHub(hass, config_entry)

    if config_entry.unique_id is None:
        hass.config_entries.async_update_entry(
            config_entry, unique_id=config_entry.data[CONF_HOST]
        )

    if CONF_REPEATER_MODE not in config_entry.data:
        hass.config_entries.async_update_entry(
            config_entry, data={**config_entry.data, CONF_REPEATER_MODE: False}
        )

    if not await hub.async_setup():
        return False

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = hub
    hass.data[DOMAIN].setdefault(CLIENTS, {})
    await hub.async_config_entry_first_refresh()
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    device_registry: DeviceRegistry = hass.helpers.device_registry.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, hub.host)},
        default_manufacturer=ATTR_MANUFACTURER,
        default_model=hub.api.model,
        default_name=hub.api.hostname,
        sw_version=hub.api.firmware,
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
