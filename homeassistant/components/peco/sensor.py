"""Sensor component for PECO outage counter."""
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Final

import async_timeout
from peco import BadJSONError, HttpError, InvalidCountyError

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import _LOGGER, DOMAIN, SCAN_INTERVAL

PARALLEL_UPDATES: Final = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    api = hass.data[DOMAIN][config_entry.entry_id]
    conf: MappingProxyType[str, Any] = config_entry.data

    async def async_update_data():
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(10):
                return await api.get_outage_count(conf["county"])
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
    county = conf["county"]
    _LOGGER.info("County: %s", county)
    async_add_entities(
        [PecoOutageCounterSensorEntity(hass, config_entry.title, county, coordinator)],
        True,
    )
    return


class PecoOutageCounterSensorEntity(CoordinatorEntity, SensorEntity):
    """PECO outage counter sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:power-plug-off"

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        county: str,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self._county = county
        self._name = name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> int:
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
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._county
