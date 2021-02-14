"""The Flipr integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Dict

from flipr_api import FliprAPIRestClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_FLIPR_ID, CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .crypt_util import decrypt_data

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)


PLATFORMS = ["sensor", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the Flipr component."""
    # Make sure coordinator is initialized.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flipr from a config entry."""
    _LOGGER.debug("async_setup_entry starting")

    coordinator = FliprDataUpdateCoordinator(hass, entry)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

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
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FliprDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to hold Flipr data retrieval."""

    def __init__(self, hass, entry):
        """Initialize."""
        username = entry.data[CONF_USERNAME]
        crypted_password = entry.data[CONF_PASSWORD]
        self.flipr_id = entry.data[CONF_FLIPR_ID]

        _LOGGER.debug("Config entry values : %s, %s", username, self.flipr_id)

        # Decrypt stored password in config.
        password = decrypt_data(crypted_password, self.flipr_id)

        # Establishes the connection.
        self.client = FliprAPIRestClient(username, password)
        self.hass = hass
        self.entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name=f"Flipr data measure for {self.flipr_id}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        return await self.hass.async_add_executor_job(
            self.client.get_pool_measure_latest, self.flipr_id
        )


class FliprEntity(CoordinatorEntity):
    """Implements a common class elements representing the Flipr component."""

    def __init__(self, coordinator, flipr_id, info_type):
        """Initialize Flipr sensor."""
        super().__init__(coordinator)
        self._unique_id = f"{flipr_id}-{info_type}"
        self.info_type = info_type
        self.flipr_id = flipr_id

    @property
    def unique_id(self):
        """Return a unique id."""
        return self._unique_id
