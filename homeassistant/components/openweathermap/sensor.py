"""Support for the OpenWeatherMap (OWM) service."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UV_INDEX,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import OpenweathermapConfigEntry
from .const import (
    ATTR_API_CLOUDS,
    ATTR_API_CONDITION,
    ATTR_API_CURRENT,
    ATTR_API_DEW_POINT,
    ATTR_API_FEELS_LIKE_TEMPERATURE,
    ATTR_API_HUMIDITY,
    ATTR_API_PRECIPITATION_KIND,
    ATTR_API_PRESSURE,
    ATTR_API_RAIN,
    ATTR_API_SNOW,
    ATTR_API_TEMPERATURE,
    ATTR_API_UV_INDEX,
    ATTR_API_VISIBILITY_DISTANCE,
    ATTR_API_WEATHER,
    ATTR_API_WEATHER_CODE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_SPEED,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    OWM_MODE_FREE_FORECAST,
)

WEATHER_SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_API_WEATHER,
        name="Weather",
    ),
    SensorEntityDescription(
        key=ATTR_API_DEW_POINT,
        name="Dew Point",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_TEMPERATURE,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_FEELS_LIKE_TEMPERATURE,
        name="Feels like temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_WIND_SPEED,
        name="Wind speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_WIND_BEARING,
        name="Wind bearing",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key=ATTR_API_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_PRESSURE,
        name="Pressure",
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_CLOUDS,
        name="Cloud coverage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_RAIN,
        name="Rain",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_SNOW,
        name="Snow",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_PRECIPITATION_KIND,
        name="Precipitation kind",
    ),
    SensorEntityDescription(
        key=ATTR_API_UV_INDEX,
        name="UV Index",
        native_unit_of_measurement=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_VISIBILITY_DISTANCE,
        name="Visibility",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_CONDITION,
        name="Condition",
    ),
    SensorEntityDescription(
        key=ATTR_API_WEATHER_CODE,
        name="Weather Code",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenweathermapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenWeatherMap sensor entities based on a config entry."""
    domain_data = config_entry.runtime_data
    name = domain_data.name
    unique_id = config_entry.unique_id
    assert unique_id is not None
    weather_coordinator = domain_data.coordinator

    if domain_data.mode == OWM_MODE_FREE_FORECAST:
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        for entry in entries:
            entity_registry.async_remove(entry.entity_id)
    else:
        async_add_entities(
            OpenWeatherMapSensor(
                name,
                unique_id,
                description,
                weather_coordinator,
            )
            for description in WEATHER_SENSOR_TYPES
        )


class AbstractOpenWeatherMapSensor(SensorEntity):
    """Abstract class for an OpenWeatherMap sensor."""

    _attr_should_poll = False
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        name: str,
        unique_id: str,
        description: SensorEntityDescription,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._coordinator = coordinator

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{unique_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            name=DEFAULT_NAME,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Get the latest data from OWM and updates the states."""
        await self._coordinator.async_request_refresh()


class OpenWeatherMapSensor(AbstractOpenWeatherMapSensor):
    """Implementation of an OpenWeatherMap sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self._coordinator.data[ATTR_API_CURRENT].get(self.entity_description.key)
