"""The Coolmaster integration."""
import logging

from pycoolmasternet_async import CoolMasterNet

from homeassistant.components.climate import SCAN_INTERVAL
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DATA_COORDINATOR, DATA_INFO, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Set up Coolmaster from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    coolmaster = CoolMasterNet(host, port)
    try:
        info = await coolmaster.info()
        if not info:
            raise ConfigEntryNotReady
    except (OSError, ConnectionRefusedError, TimeoutError) as error:
        raise ConfigEntryNotReady() from error
    coordinator = CoolmasterDataUpdateCoordinator(hass, coolmaster)
    hass.data.setdefault(DOMAIN, {})
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_INFO: info,
        DATA_COORDINATOR: coordinator,
    }
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a Coolmaster config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "climate")

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class CoolmasterDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Coolmaster data."""

    def __init__(self, hass, coolmaster):
        """Initialize global Coolmaster data updater."""
        self._coolmaster = coolmaster

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from Coolmaster."""
        try:
            return await self._coolmaster.status()
        except (OSError, ConnectionRefusedError, TimeoutError) as error:
            raise UpdateFailed from error
