"""The Brother component."""
import asyncio
from datetime import timedelta
import logging

from brother import Brother, SnmpError, UnsupportedModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TYPE, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

PLATFORMS = ["sensor"]

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Config):
    """Set up the Brother component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Brother from a config entry."""
    host = entry.data[CONF_HOST]
    kind = entry.data[CONF_TYPE]

    coordinator = BrotherDataUpdateCoordinator(hass, host=host, kind=kind)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        coordinator.shutdown()
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id).shutdown()

    return unload_ok


class BrotherDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Brother data from the printer."""

    def __init__(self, hass, host, kind):
        """Initialize."""
        self.brother = Brother(host, kind=kind)
        self._unsub_stop = hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, self._handle_ha_stop
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Update data via library."""
        # Race condition on shutdown. Stop all the fetches.
        if self._unsub_stop is None:
            return None

        try:
            await self.brother.async_update()
        except (ConnectionError, SnmpError, UnsupportedModel) as error:
            raise UpdateFailed(error) from error
        return self.brother.data

    def shutdown(self):
        """Shutdown the Brother coordinator."""
        self._unsub_stop()
        self._unsub_stop = None
        self.brother.shutdown()

    def _handle_ha_stop(self, _):
        """Handle Home Assistant stopping."""
        self.shutdown()
