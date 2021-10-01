"""The Flipr integration."""
from datetime import timedelta
import logging

from flipr_api import FliprAPIRestClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, CONF_FLIPR_ID, DOMAIN, MANUFACTURER, NAME

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)


PLATFORMS = ["binary_sensor", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flipr from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = FliprDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FliprDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to hold Flipr data retrieval."""

    def __init__(self, hass, entry):
        """Initialize."""
        username = entry.data[CONF_EMAIL]
        password = entry.data[CONF_PASSWORD]
        self.flipr_id = entry.data[CONF_FLIPR_ID]

        # Establishes the connection.
        self.client = FliprAPIRestClient(username, password)
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

    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    def __init__(
        self, coordinator: DataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize Flipr sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        if coordinator.config_entry:
            flipr_id = coordinator.config_entry.data[CONF_FLIPR_ID]
            self._attr_unique_id = f"{flipr_id}-{description.key}"

            self._attr_device_info = {
                "identifiers": {(DOMAIN, flipr_id)},
                "name": NAME,
                "manufacturer": MANUFACTURER,
            }

            self._attr_name = f"Flipr {flipr_id} {description.name}"
