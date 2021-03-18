""""Home Assistant component for accessing the Wallbox Portal API, the switch component allows pausing/resuming and lock/unlock.
    """

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from datetime import timedelta
from homeassistant.components.number import NumberEntity
from homeassistant.components.number import PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_NAME
from wallbox import Wallbox

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, CONF_STATION, CONF_CONNECTIONS


_LOGGER = logging.getLogger(__name__)


def wallbox_updater(wallbox, station):

    w = wallbox
    data = w.getChargerStatus(station)
    max_charger_current = data["config_data"]["max_charging_current"]
    return max_charger_current


async def async_setup_entry(hass, config, async_add_entities):

    wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]

    name = config.title
    station = config.data[CONF_STATION]

    async def async_update_data():

        try:
            return await hass.async_add_executor_job(wallbox_updater, wallbox, station)

        except:
            _LOGGER.error("Error getting data from wallbox API")
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
            WallboxMaxChargingCurrent(
                f"{name} Max. Charging Current", config, coordinator, wallbox
            )
        ]
    )


class WallboxMaxChargingCurrent(CoordinatorEntity, NumberEntity):
    """Representation of the Wallbox Pause Switch."""

    def __init__(self, name, config, coordinator, wallbox):
        super().__init__(coordinator)
        self._wallbox = wallbox
        self._is_on = False
        self._name = name
        self.station = config.data[CONF_STATION]

    def set_max_charging_current(self, max_charging_current, wallbox):

        try:
            w = wallbox
            """"unlock charger"""
            _LOGGER.debug("Unlocking Wallbox")
            w.setMaxChargingCurrent(self.station, max_charging_current)

        except Exception as exception:
            _LOGGER.error("Unable to pause/resume Wallbox. %s", exception)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def icon(self):
        return "mdi:ev-station"

    @property
    def value(self):
        return self.coordinator.data

    def set_value(self, value: float):
        self.set_max_charging_current(value, self._wallbox)
