"""Sensor component for PECO outage counter."""
import asyncio
from datetime import timedelta
from types import MappingProxyType
from typing import Any, Final, cast

from peco import BadJSONError, HttpError

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

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
    api = hass.data[DOMAIN][config_entry.entry_id]
    websession = async_get_clientsession(hass)
    conf: MappingProxyType[str, Any] = config_entry.data

    async def async_update_data() -> dict[str, float]:
        """Fetch data from API."""
        if conf["county"] == "TOTAL":
            try:
                data = cast(dict[str, float], await api.get_outage_totals(websession))
            except HttpError as err:
                raise UpdateFailed(f"Error fetching data: {err}") from err
            except BadJSONError as err:
                raise UpdateFailed(f"Error parsing data: {err}") from err
            except asyncio.TimeoutError as err:
                raise UpdateFailed(f"Timeout fetching data: {err}") from err
            if data["percent_customers_out"] < 5:
                percent_out = data["customers_out"] / data["customers_served"] * 100
                data["percent_customers_out"] = percent_out
            return data
        try:
            county_data = cast(
                dict[str, float],
                await api.get_outage_count(conf["county"], websession),
            )
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
        LOGGER,
        name="PECO Outage Count",
        update_method=async_update_data,
        update_interval=timedelta(minutes=SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    county = conf["county"]

    async_add_entities(
        [PecoSensor(hass, sensor, county, coordinator) for sensor in SENSOR_LIST],
        True,
    )
    return


class PecoSensor(CoordinatorEntity[dict[str, float]], SensorEntity):
    """PECO outage counter sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:power-plug-off"

    def __init__(
        self,
        hass: HomeAssistant,
        description: SensorEntityDescription,
        county: str,
        coordinator: DataUpdateCoordinator[dict[str, float]],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self._county = county
        self._attr_name = f"{county.capitalize()} {description.name}"
        self._attr_unique_id = f"{self._county}-{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Return the value of the sensor."""
        return self.coordinator.data[self.entity_description.key]
