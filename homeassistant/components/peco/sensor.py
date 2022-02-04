"""Sensor component for PECO outage counter."""
import asyncio
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Final

from peco import BadJSONError, HttpError

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import _LOGGER, DOMAIN, SCAN_INTERVAL

PARALLEL_UPDATES: Final = 0
SENSOR_LIST = (
    SensorEntityDescription(key="customers_out", name="Customers Out"),
    SensorEntityDescription(
        key="percent_customers_out",
        name="Percent Customers Out",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(key="outage_count", name="Outage Count"),
    SensorEntityDescription(key="customers_served", name="Customers Served"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    websession = hass.data[DOMAIN][config_entry.entry_id]["websession"]
    conf: MappingProxyType[str, Any] = config_entry.data

    async def async_update_data() -> dict:
        """Fetch data from API."""
        if conf["county"] == "TOTAL":
            try:
                data: dict = await api.get_outage_totals(websession)
            except HttpError as err:
                raise UpdateFailed(f"Error fetching data: {err}") from err
            except BadJSONError as err:
                raise UpdateFailed(f"Error parsing data: {err}") from err
            except asyncio.TimeoutError as err:
                raise UpdateFailed(f"Timeout fetching data: {err}") from err
            if data["percent_customers_out"] < 5:
                data["percent_customers_out"] = "Less than 5%"
            return data
        try:
            county_data: dict = await api.get_outage_count(conf["county"], websession)
        except HttpError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        except BadJSONError as err:
            raise UpdateFailed(f"Error parsing data: {err}") from err
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout fetching data: {err}") from err
        if county_data["percent_customers_out"] < 5:
            percent_out = (
                county_data["customers_out"] / county_data["customers_served"] * 100
            )
            county_data["percent_customers_out"] = percent_out
        return county_data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="PECO Outage Count",
        update_method=async_update_data,
        update_interval=timedelta(minutes=SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    county = conf["county"]

    sensors = []
    for sensor in SENSOR_LIST:
        sensors.append(PecoSensor(hass, sensor, county, coordinator))
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
        description: SensorEntityDescription,
        county: str,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self._county = county
        self._attr_name = f"{county.capitalize()} {description.name}"
        self._attr_unique_id = f"{self._county}_{description.key}"
        self._key = description.key
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self) -> int:
        """Return the value of the sensor."""
        data: int = self.coordinator.data[self._key]
        return data
