"""Sensor for the zamg integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_STATION,
    ATTR_UPDATED,
    ATTRIBUTION,
    CONF_STATION_ID,
    DOMAIN,
    MANUFACTURER_URL,
)
from .coordinator import ZamgDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class ZamgSensorEntityDescription(SensorEntityDescription):
    """Describes Zamg sensor entity."""

    para_name: str


SENSOR_TYPES: tuple[ZamgSensorEntityDescription, ...] = (
    ZamgSensorEntityDescription(
        key="pressure",
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="P",
    ),
    ZamgSensorEntityDescription(
        key="pressure_sealevel",
        name="Pressure at Sea Level",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="PRED",
    ),
    ZamgSensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="RFAM",
    ),
    ZamgSensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="FFAM",
    ),
    ZamgSensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        para_name="DD",
    ),
    ZamgSensorEntityDescription(
        key="wind_max_speed",
        name="Top Wind Speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="FFX",
    ),
    ZamgSensorEntityDescription(
        key="wind_max_bearing",
        name="Top Wind Bearing",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="DDX",
    ),
    ZamgSensorEntityDescription(
        key="sun_last_10min",
        name="Sun Last 10 Minutes",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="SO",
    ),
    ZamgSensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="TL",
    ),
    ZamgSensorEntityDescription(
        key="temperature_average",
        name="Temperature Average",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="TLAM",
    ),
    ZamgSensorEntityDescription(
        key="precipitation",
        name="Precipitation",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="RR",
    ),
    ZamgSensorEntityDescription(
        key="snow",
        name="Snow",
        native_unit_of_measurement=UnitOfPrecipitationDepth.CENTIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="SCHNEE",
    ),
    ZamgSensorEntityDescription(
        key="dewpoint",
        name="Dew Point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="TP",
    ),
    ZamgSensorEntityDescription(
        key="dewpoint_average",
        name="Dew Point Average",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        para_name="TPAM",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

API_FIELDS: list[str] = [desc.para_name for desc in SENSOR_TYPES]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
        self,
        coordinator: ZamgDataUpdateCoordinator,
        name: str,
        station_id: str,
        description: ZamgSensorEntityDescription,
    ) -> None:
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
            name=name,
        )
        coordinator.api_fields = API_FIELDS

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        try:
            return self.coordinator.data[self.station_id][
                self.entity_description.para_name
            ]["data"]
        except KeyError:
            return None

    @property
    def extra_state_attributes(self) -> Mapping[str, str]:
        """Return the state attributes."""
        if (update_time := self.coordinator.data["last_update"]) is not None:
            update_time = update_time.isoformat()
        return {
            ATTR_STATION: self.coordinator.data["Name"],
            ATTR_UPDATED: update_time,
        }
