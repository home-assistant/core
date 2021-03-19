"""Home Assistant component for accessing the Wallbox Portal API, the switch component allows pausing/resuming and lock/unlock."""

from datetime import timedelta
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_CONNECTIONS, CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)


def wallbox_updater(wallbox, station):
    """Get new data for Wallbox component."""

    data = wallbox.getChargerStatus(station)
    status_description = data["status_description"].lower()
    return status_description


async def async_setup_entry(hass, config, async_add_entities):
    """Create wallbox switch entities in HASS."""

    wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]
    name = config.title
    station = config.data[CONF_STATION]

    async def async_update_data():

        try:
            return await hass.async_add_executor_job(wallbox_updater, wallbox, station)

        except ConnectionError as exception:
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
        """Initialize a Wallbox switch."""
        super().__init__(coordinator)
        self._wallbox = wallbox
        self._name = name
        self.station = config.data[CONF_STATION]

    def pause_charger(self, pause):
        """Pause / Resume Charger using API."""
        try:

            station = self.station
            wallbox = self._wallbox

            if pause is False:
                _LOGGER.debug("Unlocking Wallbox")
                wallbox.resumeChargingSession(station)

            elif pause is True:
                _LOGGER.debug("Locking Wallbox")
                wallbox.pauseChargingSession(station)

        except ConnectionError as exception:
            _LOGGER.error("Unable to pause/resume Wallbox. %s", exception)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the switch."""
        if self.coordinator.data == "charging":
            return "mdi:motion-play-outline"
        if self.coordinator.data == "connected":
            return "mdi:motion-pause-outline"
        return "mdi:power-plug-off-outline"

    @property
    def is_on(self):
        """Return the status of the switch."""
        return self.coordinator.data.lower() not in [
            "offline",
            "error",
            "ready",
            "charging",
        ]

    @property
    def available(self):
        """Return the availability of the switch."""
        return self.coordinator.data.lower() not in ["offline", "error", "ready"]

    def turn_on(self, **kwargs):
        """Turn switch on."""
        if self.coordinator.data.lower() == "charging":
            self.pause_charger(True)
        else:
            _LOGGER.debug("Not charging, cannot pause, doing nothing")

    def turn_off(self, **kwargs):
        """Turn switch off."""
        if self.coordinator.data.lower() not in [
            "offline",
            "error",
            "ready",
            "charging",
        ]:
            self.pause_charger(False)
        else:
            _LOGGER.debug("Status is not 'connected', cannot unpause, doing nothing")
