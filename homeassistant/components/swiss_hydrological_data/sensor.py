"""Support for hydrological data from the Fed. Office for the Environment."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from requests.exceptions import RequestException
from swisshydrodata import SwissHydroData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import Throttle

from .const import (
    CONF_STATION,
    DOMAIN,
    SENSOR_DISCHARGE,
    SENSOR_LEVEL,
    SENSOR_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

ATTR_MAX_24H = "max_24h"
ATTR_MEAN_24H = "mean_24h"
ATTR_MIN_24H = "min_24h"
ATTR_STATION_UPDATE = "station_update"
ATTR_WATER_BODY_TYPE = "water_body_type"


@dataclass(frozen=True, kw_only=True)
class SwissHydroSensorEntityDescription(SensorEntityDescription):
    """Describes a Swiss Hydrological Data sensor entity."""

    condition: str


SENSORS: tuple[SwissHydroSensorEntityDescription, ...] = (
    SwissHydroSensorEntityDescription(
        key=SENSOR_DISCHARGE,
        translation_key=SENSOR_DISCHARGE,
        condition=SENSOR_DISCHARGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SwissHydroSensorEntityDescription(
        key=SENSOR_LEVEL,
        translation_key=SENSOR_LEVEL,
        condition=SENSOR_LEVEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SwissHydroSensorEntityDescription(
        key=SENSOR_TEMPERATURE,
        translation_key=SENSOR_TEMPERATURE,
        condition=SENSOR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Swiss Hydrological Data sensors based on a config entry."""
    station_id = entry.data[CONF_STATION]
    hydro_data = HydrologicalData(station_id)
    try:
        await hass.async_add_executor_job(hydro_data.update)
    except RequestException as err:
        raise ConfigEntryNotReady(
            "Cannot connect to the Swiss Hydrological Data service"
        ) from err

    if hydro_data.data is None:
        return

    async_add_entities(
        SwissHydrologicalDataSensor(hydro_data, description, entry)
        for description in SENSORS
        if description.condition in hydro_data.data.get("parameters", {})
    )


class HydrologicalData:
    """Representation of the hydrological data."""

    def __init__(self, station_id: int) -> None:
        """Initialize the data object."""
        self._station_id = station_id
        self.data: dict[str, Any] | None = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data from the Swiss Federal Office for the Environment."""
        self.data = SwissHydroData().get_station(self._station_id)


class SwissHydrologicalDataSensor(SensorEntity):
    """Representation of a Swiss Hydrological Data sensor."""

    entity_description: SwissHydroSensorEntityDescription
    _attr_attribution = (
        "Data provided by the Swiss Federal Office for the Environment FOEN"
    )
    _attr_has_entity_name = True

    def __init__(
        self,
        hydro_data: HydrologicalData,
        description: SwissHydroSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._hydro_data = hydro_data
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(entry.data[CONF_STATION]))},
            manufacturer="Swiss Federal Office for the Environment FOEN",
            name=entry.title,
        )

    def _get_condition_data(self) -> dict[str, Any]:
        """Return data for this sensor's condition."""
        if self._hydro_data.data is None:
            return {}
        return self._hydro_data.data.get("parameters", {}).get(
            self.entity_description.condition, {}
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._hydro_data.data is not None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._get_condition_data().get("unit")

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self._get_condition_data().get("value")
        if isinstance(value, (int, float)):
            return round(value, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        condition_data = self._get_condition_data()
        if not condition_data:
            return {}

        return {
            ATTR_WATER_BODY_TYPE: self._hydro_data.data.get("water-body-type")
            if self._hydro_data.data
            else None,
            ATTR_STATION_UPDATE: condition_data.get("datetime"),
            ATTR_MAX_24H: condition_data.get("max-24h"),
            ATTR_MEAN_24H: condition_data.get("mean-24h"),
            ATTR_MIN_24H: condition_data.get("min-24h"),
        }

    async def async_update(self) -> None:
        """Update sensor data."""
        await self.hass.async_add_executor_job(self._hydro_data.update)
