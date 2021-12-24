"""The Starlink integration."""
from __future__ import annotations

from abc import ABC
from datetime import timedelta
import logging

import async_timeout
from spacex.starlink import CommunicationError, StarlinkDish
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_DEFAULT_ADDRESS,
    CONF_DEFAULT_NAME,
    CONF_DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["binary_sensor", "sensor"]
PLATFORM_SCHEMA = {
    vol.Optional(CONF_NAME, default=CONF_DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ADDRESS, default=CONF_DEFAULT_ADDRESS): cv.string,
    vol.Optional(
        CONF_SCAN_INTERVAL, default=CONF_DEFAULT_SCAN_INTERVAL
    ): cv.positive_float,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Starlink from a config entry."""
    dish = StarlinkDish(address=entry.data[CONF_ADDRESS], autoconnect=True)

    async def async_update_data():
        async with async_timeout.timeout(10):
            try:
                if not dish.connected:
                    dish.connect(refresh=False)  # Avoid refreshing twice
                dish.refresh()
            except CommunicationError as err:
                _LOGGER.warning("Lost connection to Dishy")
                dish.close()
                raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=entry.data[CONF_NAME],
        update_method=async_update_data,
        update_interval=timedelta(seconds=entry.data[CONF_SCAN_INTERVAL] or 5),
    )

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = (dish, coordinator)

    await coordinator.async_refresh()
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


class BaseStarlinkEntity(CoordinatorEntity, ABC):
    """Base entity for all starlink entities.

    Contains a StarlinkDish and a coordinator to fetch updates from it.
    """

    base_name: str = NotImplemented

    def __init__(self, coordinator: DataUpdateCoordinator, dish: StarlinkDish):
        """Initialize.

        Parameters
        ----------
        coordinator : DataUpdateCoordinator
            The coordinator that is handling the data updates

        dish : StarlinkDish
            The API for communicating with the Starlink Dish, agnostic of protocol.

        """
        super().__init__(coordinator)
        self.dish = dish

    async def async_added_to_hass(self):
        """Handle entities being added to Home Assistant.

        This ensure a connection is not made unless there are active entities that will need to be updated.
        """
        await super().async_added_to_hass()
        if not self.dish.connected:
            self.dish.connect()

        # TODO: Disconnect if the last entity is removed

    @property
    def device_info(self):
        """Information about the satellite."""
        return {
            "identifiers": {(DOMAIN, self.dish.id)},
            "name": self.coordinator.name,
            "model": "Dishy McFlatface",
            "manufacturer": "SpaceX",
            "sw_version": self.dish.software_version,
            "hw_version": self.dish.hardware_version,
            "configuration_url": "http://" + self.dish.address.split(":")[0] + ":80",
        }

    @property
    def name(self):
        """Return the name of the entity.

        By default, combines the base_name attribute of the class with the name of the device.
        """
        return self.device_info["name"] + " " + self.base_name

    @property
    def available(self):
        """Return whether or not a connection to the dish could be made."""
        return self.dish.connected


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
