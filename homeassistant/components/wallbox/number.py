"""Home Assistant component for accessing the Wallbox Portal API, the number component allows set charging power."""

from datetime import timedelta
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_CONNECTIONS, CONF_STATION, DOMAIN

_LOGGER = logging.getLogger(__name__)


def wallbox_updater(wallbox, station):
    """Get new data for Wallbox component."""

    wallbox = wallbox
    data = wallbox.getChargerStatus(station)
    max_charger_current = data["config_data"]["max_charging_current"]
    return max_charger_current


async def async_setup_entry(hass, config, async_add_entities):
    """Create wallbox switch entities in HASS."""

    wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]

    name = config.title
    station = config.data[CONF_STATION]

    async def async_update_data():

        try:
            return await hass.async_add_executor_job(wallbox_updater, wallbox, station)

        except ConnectionError:
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
        """Initialize a Wallbox lock."""
        super().__init__(coordinator)
        self._wallbox = wallbox
        self._is_on = False
        self._name = name
        self.station = config.data[CONF_STATION]

    def set_max_charging_current(self, max_charging_current):
        """Set max charging current using API."""

        try:
            wallbox = self._wallbox
            _LOGGER.debug("Setting charging current.")
            wallbox.setMaxChargingCurrent(self.station, max_charging_current)

        except ConnectionError as exception:
            _LOGGER.error("Unable to set charging current. %s", exception)

    @property
    def name(self):
        """Return the name of the number entity."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the entity."""
        return "mdi:ev-station"

    @property
    def value(self):
        """Return the value of the entity."""
        return self.coordinator.data

    def set_value(self, value: float):
        """Set the value of the entity."""
        self.set_max_charging_current(value, self._wallbox)
