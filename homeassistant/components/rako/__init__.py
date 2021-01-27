"""The Rako integration."""
import logging

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.rako.bridge import RakoBridge
from homeassistant.components.rako.const import (
    CONF_MAC_ADDRESS,
    DATA_RAKO_BRIDGE_CLIENT,
    DATA_RAKO_LIGHT_MAP,
    DATA_RAKO_LISTENER_TASK,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Rako component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rako from a config entry."""
    bridge = RakoBridge(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_MAC_ADDRESS],
        entry.entry_id,
        hass,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_RAKO_BRIDGE_CLIENT: bridge,
        DATA_RAKO_LIGHT_MAP: {},
        DATA_RAKO_LISTENER_TASK: None,
    }

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, LIGHT_DOMAIN)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, LIGHT_DOMAIN)

    del hass.data[DOMAIN][entry.entry_id]
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return True
