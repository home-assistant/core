""""Home Assistant component for accessing the Wallbox Portal API, the switch component allows pausing/resuming and lock/unlock.
    """

import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from datetime import timedelta
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_NAME
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from wallbox import Wallbox

from .const import DOMAIN, CONF_STATION, CONF_CONNECTIONS


_LOGGER = logging.getLogger(__name__)


def wallbox_updater(wallbox, station):

    w = wallbox
    data = w.getChargerStatus(station)
    status_description = data["status_description"].lower()
    return status_description


async def async_setup_entry(hass, config, async_add_entities):

    wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]
    name = config.title
    station = config.data[CONF_STATION]

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
            WallboxPause(
                f"{name} Pause",
                config,
                coordinator,
                wallbox,
            )
        ]
    )


class WallboxPause(CoordinatorEntity, SwitchEntity):
    """Representation of the Wallbox Pause Switch."""

    def __init__(self, name, config, coordinator, wallbox):
        super().__init__(coordinator)
        self._wallbox = wallbox
        self._name = name
        self.station = config.data[CONF_STATION]

    def pause_charger(self, pause):
        """Pause / Resume Charger using API"""

        try:

            station = self.station
            w = self._wallbox

            if pause is False:
                """"unlock charger"""
                _LOGGER.debug("Unlocking Wallbox")
                w.resumeChargingSession(station)

            elif pause is True:
                """"lock charger"""
                _LOGGER.debug("Locking Wallbox")
                w.pauseChargingSession(station)

        except Exception as exception:
            _LOGGER.error("Unable to pause/resume Wallbox. %s", exception)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def icon(self):
        if self.coordinator.data == "charging":
            return "mdi:motion-play-outline"
        elif self.coordinator.data == "connected":
            return "mdi:motion-pause-outline"
        else:
            return "mdi:power-plug-off-outline"

    @property
    def is_on(self):
        return self.coordinator.data.lower() not in [
            "offline",
            "error",
            "ready",
            "charging",
        ]

    @property
    def available(self):
        return self.coordinator.data.lower() not in ["offline", "error", "ready"]

    def turn_on(self, **kwargs):
        if self.coordinator.data.lower() == "charging":
            self.pause_charger(True)
        else:
            _LOGGER.debug("Not charging, cannot pause, doing nothing")

    def turn_off(self, **kwargs):
        if self.coordinator.data.lower() not in [
            "offline",
            "error",
            "ready",
            "charging",
        ]:
            self.pause_charger(False)
        else:
            _LOGGER.debug("Status is not 'connected', cannot unpause, doing nothing")
