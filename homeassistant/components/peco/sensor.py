"""Sensor component for PECO outage counter."""
from datetime import timedelta

import async_timeout

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import _LOGGER, DOMAIN, SCAN_INTERVAL
from .peco_outage_api import BadJSONError, HttpError, InvalidCountyError

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    api = hass.data[DOMAIN][config_entry.entry_id]

    async def async_update_data():
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(10):
                return await api.get_outage_count()
        except InvalidCountyError as err:
            raise ConfigEntryAuthFailed from err
        except HttpError as err:
            raise UpdateFailed from err
        except BadJSONError as err:
            raise UpdateFailed from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="PECO Outage Count",
        update_method=async_update_data,
        update_interval=timedelta(minutes=SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    _LOGGER.info("Setting up sensor platform")
    conf = config_entry.data
    county = conf["county"]
    _LOGGER.info("County: %s", county)
    async_add_entities(
        [PecoOutageCounterSensorEntity(hass, config_entry.title, county, coordinator)],
        True,
    )
    return True


class PecoOutageCounterSensorEntity(CoordinatorEntity, SensorEntity):
    """PECO outage counter sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:power-plug-off"

    def __init__(self, hass, name, county, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self._county = county
        self._name = name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the value of the sensor."""
        return self.coordinator.data["customers_out"]

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.coordinator.data["percent_customers_out"] < 5:
            percent_customers_out = "Less than 5%"
        else:
            percent_customers_out = (
                str(self.coordinator.data["percent_customers_out"]) + "%"
            )
        return {
            "percent_customers_out": percent_customers_out,
            "outage_count": self.coordinator.data["outage_count"],
            "customers_served": self.coordinator.data["customers_served"],
        }

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._county
