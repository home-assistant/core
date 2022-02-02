"""Sensor component for PECO outage counter."""
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Final

import async_timeout
from peco import BadJSONError, HttpError

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import _LOGGER, DOMAIN, SCAN_INTERVAL, SENSOR_LIST

PARALLEL_UPDATES: Final = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    websession = hass.data[DOMAIN][config_entry.entry_id]["websession"]
    conf: MappingProxyType[str, Any] = config_entry.data

    async def async_update_data():
        """Fetch data from API."""
        async with async_timeout.timeout(10):
            if conf["county"] == "TOTAL":
                try:
                    data = await api.get_outage_totals(websession)
                except HttpError as err:
                    raise UpdateFailed(f"Error fetching data: {err}") from err
                except BadJSONError as err:
                    raise UpdateFailed(f"Error parsing data: {err}") from err
                if data["percent_customers_out"] < 5:
                    data["percent_customers_out"] = "Less than 5%"
                return data
            try:
                data = await api.get_outage_count(conf["county"], websession)
            except HttpError as err:
                raise UpdateFailed from err
            except BadJSONError as err:
                raise UpdateFailed from err
            if data["percent_customers_out"] < 5:
                data["percent_customers_out"] = "Less than 5%"
            return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="PECO Outage Count",
        update_method=async_update_data,
        update_interval=timedelta(minutes=SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    county = conf["county"]

    county_name = county.lower()[0].upper() + county.lower()[1:]

    sensors = []
    for sensor in SENSOR_LIST:
        sensor_name = getattr(sensor, "name", "This should never happen").format(
            county_name
        )
        sensors.append(PecoSensor(hass, sensor_name, county, coordinator, sensor.key))
    async_add_entities(
        sensors,
        True,
    )
    return


class PecoSensor(CoordinatorEntity, SensorEntity):
    """PECO outage counter sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:power-plug-off"

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        county: str,
        coordinator: DataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self._county = county
        self._attr_name = name
        self._attr_unique_id = f"{self._county}_{key}"
        self._key = key

    @property
    def native_value(self) -> int:
        """Return the value of the sensor."""
        return self.coordinator.data[self._key]
