"""The Homewizard integration."""
import logging

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .coordinator import HWEnergyDeviceUpdateCoordinator as Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homewizard from a config entry."""
    coordinator = Coordinator(hass, entry, entry.data[CONF_IP_ADDRESS])
    try:
        await coordinator.async_config_entry_first_refresh()

    except ConfigEntryNotReady:
        await coordinator.api.close()

        if coordinator.api_disabled:
            entry.async_start_reauth(hass)

        raise

    # Abort reauth config flow if active
    for progress_flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        if progress_flow["context"].get("source") == SOURCE_REAUTH:
            hass.config_entries.flow.async_abort(progress_flow["flow_id"])

    # Setup entry
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Finalize
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("__init__ async_unload_entry")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()

    return unload_ok
