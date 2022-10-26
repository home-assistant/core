"""Sensor for zamg the Austrian "Zentralanstalt für Meteorologie und Geodynamik" integration."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Union

import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEGREE,
    LENGTH_CENTIMETERS,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_HPA,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_STATION,
    ATTR_UPDATED,
    ATTRIBUTION,
    CONF_STATION_ID,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER_URL,
)

_DType = Union[type[int], type[float], type[str]]


@dataclass
class ZamgRequiredKeysMixin:
    """Mixin for required keys."""

    para_name: str
    dtype: _DType


@dataclass
class ZamgSensorEntityDescription(SensorEntityDescription, ZamgRequiredKeysMixin):
    """Describes Zamg sensor entity."""


SENSOR_TYPES: tuple[ZamgSensorEntityDescription, ...] = (
    ZamgSensorEntityDescription(
        key="pressure",
        name="Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="P",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="pressure_sealevel",
        name="Pressure at Sea Level",
        native_unit_of_measurement=PRESSURE_HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="PRED",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="RFAM",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="FFAM",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="DD",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="wind_max_speed",
        name="Top Wind Speed",
        native_unit_of_measurement=SPEED_METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="FFX",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="wind_max_bearing",
        name="Top Wind Bearing",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="DDX",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="sun_last_10min",
        name="Sun Last 10 Minutes",
        native_unit_of_measurement=TIME_SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="SO",
        dtype=int,
    ),
    ZamgSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="TL",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="temperature_average",
        name="Temperature Average",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="TLAM",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="precipitation",
        name="Precipitation",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="RR",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="snow",
        name="Snow",
        native_unit_of_measurement=LENGTH_CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="SCHNEE",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="dewpoint",
        name="Dew Point",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="TP",
        dtype=float,
    ),
    ZamgSensorEntityDescription(
        key="dewpoint_average",
        name="Dew Point Average",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="TPAM",
        dtype=float,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

API_FIELDS: dict[str, tuple[str, _DType]] = {
    desc.para_name: (desc.key, desc.dtype) for desc in SENSOR_TYPES
}

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_CONDITIONS, default=["temperature"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_STATION_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ZAMG sensor platform."""
    # trigger import flow
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ZAMG sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        ZamgSensor(coordinator, entry.title, entry.data[CONF_STATION_ID], description)
        for description in SENSOR_TYPES
    )


class ZamgSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a ZAMG sensor."""

    _attr_attribution = ATTRIBUTION
    entity_description: ZamgSensorEntityDescription

    def __init__(
        self, coordinator, name, station_id, description: ZamgSensorEntityDescription
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{station_id}_{description.key}"
        self.station_id = f"{station_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, station_id)},
            manufacturer=ATTRIBUTION,
            configuration_url=MANUFACTURER_URL,
            name=coordinator.name,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.data[self.station_id].get(
            self.entity_description.para_name
        )["data"]

    @property
    def extra_state_attributes(self) -> Mapping[str, str]:
        """Return the state attributes."""
        update_time = self.coordinator.data.get("last_update", "")
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATION: self.coordinator.data.get("Name"),
            CONF_STATION_ID: self.station_id,
            ATTR_UPDATED: update_time.isoformat(),
        }
