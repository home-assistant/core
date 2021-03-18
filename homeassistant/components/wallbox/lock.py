""""Home Assistant component for accessing the Wallbox Portal API, the switch component allows pausing/resuming and lock/unlock.
    """

import logging

from datetime import timedelta
from homeassistant.components.lock import LockEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, CONF_STATION, CONF_CONNECTIONS


_LOGGER = logging.getLogger(__name__)


def wallbox_updater(wallbox, station):

    w = wallbox
    data = w.getChargerStatus(station)
    charger_locked = data["config_data"]["locked"]
    return charger_locked


async def async_setup_entry(hass, config, async_add_entities):

    wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]
    station = config.data[CONF_STATION]
    name = config.title

    async def async_update_data():

        try:
            return await hass.async_add_executor_job(wallbox_updater, wallbox, station)

        except Exception as exception:
            _LOGGER.error("Unable to fetch data from Wallbox Switch. %s", exception)
            return

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="wallbox",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=15),
    )

    await coordinator.async_refresh()

    async_add_entities(
        [
            WallboxLock(
                f"{name} Lock",
                config,
                coordinator,
                wallbox,
            )
        ]
    )


class WallboxLock(CoordinatorEntity, LockEntity):
    """Representation of the Wallbox portal."""

    def __init__(self, name, config, coordinator, wallbox):
        super().__init__(coordinator)
        self._wallbox = wallbox
        self._name = name
        self.station = config.data[CONF_STATION]

    async def lock_charger(self, lock):
        """Lock / Unlock charger using API"""

        try:
            station = self.station
            w = self._wallbox

            if lock is False:
                """"unlock charger"""
                _LOGGER.debug("Unlocking Wallbox")
                self.hass.async_add_executor_job(w.unlockCharger, station)

            elif lock is True:
                """"lock charger"""
                _LOGGER.debug("Locking Wallbox")
                self.hass.async_add_executor_job(w.lockCharger, station)

        except Exception as exception:
            _LOGGER.error("Unable to fetch data from Wallbox. %s", exception)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def icon(self):
        if self.coordinator.data:
            return "mdi:lock"
        else:
            return "mdi:lock-open"

    @property
    def is_locked(self):
        return self.coordinator.data

    async def async_lock(self, **kwargs):
        await self.lock_charger(True)
        self.coordinator.async_set_updated_data(True)

    async def async_unlock(self, **kwargs):
        self.coordinator.data = False
        await self.lock_charger(False)
        self.coordinator.async_set_updated_data(False)
