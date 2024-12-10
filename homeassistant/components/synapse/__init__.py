import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .synapse.bridge import SynapseBridge
from .synapse.const import DOMAIN, PLATFORMS

logger = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Synapse app from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    bridge = None

    if config_entry.entry_id not in domain_data:
        bridge = SynapseBridge(hass, config_entry)
        domain_data[config_entry.entry_id] = bridge
    else:
        bridge = domain_data[config_entry.entry_id]

    await bridge.async_reload()

    # adapter is ready to hand off data to entities
    # - devices up to date
    # - old entities removed
    await hass.config_entries.async_forward_entry_setups(
        config_entry,
        PLATFORMS
    )
    return True

async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    bridge: SynapseBridge = hass.data.setdefault(DOMAIN, {})[config_entry.entry_id]
    await bridge.async_cleanup()
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)


    return unload_ok
