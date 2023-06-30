"""Support for the Airly sensor service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_NAME,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirlyDataUpdateCoordinator
from .const import (
    ATTR_ADVICE,
    ATTR_API_ADVICE,
    ATTR_API_CAQI,
    ATTR_API_CAQI_DESCRIPTION,
    ATTR_API_CAQI_LEVEL,
    ATTR_API_CO,
    ATTR_API_HUMIDITY,
    ATTR_API_NO2,
    ATTR_API_O3,
    ATTR_API_PM1,
    ATTR_API_PM10,
    ATTR_API_PM25,
    ATTR_API_PRESSURE,
    ATTR_API_SO2,
    ATTR_API_TEMPERATURE,
    ATTR_DESCRIPTION,
    ATTR_LEVEL,
    ATTR_LIMIT,
    ATTR_PERCENT,
    ATTRIBUTION,
    DOMAIN,
    MANUFACTURER,
    SUFFIX_LIMIT,
    SUFFIX_PERCENT,
    URL,
)

PARALLEL_UPDATES = 1


@dataclass
class AirlySensorEntityDescription(SensorEntityDescription):
    """Class describing Airly sensor entities."""

    attrs: Callable[[dict[str, Any]], dict[str, Any]] = lambda data: {}


SENSOR_TYPES: tuple[AirlySensorEntityDescription, ...] = (
    AirlySensorEntityDescription(
        key=ATTR_API_CAQI,
        icon="mdi:air-filter",
        translation_key="caqi",
        native_unit_of_measurement="CAQI",
        suggested_display_precision=0,
        attrs=lambda data: {
            ATTR_LEVEL: data[ATTR_API_CAQI_LEVEL],
            ATTR_ADVICE: data[ATTR_API_ADVICE],
            ATTR_DESCRIPTION: data[ATTR_API_CAQI_DESCRIPTION],
        },
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PM1,
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PM25,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        attrs=lambda data: {
            ATTR_LIMIT: data[f"{ATTR_API_PM25}_{SUFFIX_LIMIT}"],
            ATTR_PERCENT: round(data[f"{ATTR_API_PM25}_{SUFFIX_PERCENT}"]),
        },
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PM10,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        attrs=lambda data: {
            ATTR_LIMIT: data[f"{ATTR_API_PM10}_{SUFFIX_LIMIT}"],
            ATTR_PERCENT: round(data[f"{ATTR_API_PM10}_{SUFFIX_PERCENT}"]),
        },
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_CO,
        translation_key="co",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        attrs=lambda data: {
            ATTR_LIMIT: data[f"{ATTR_API_CO}_{SUFFIX_LIMIT}"],
            ATTR_PERCENT: round(data[f"{ATTR_API_CO}_{SUFFIX_PERCENT}"]),
        },
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_NO2,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        attrs=lambda data: {
            ATTR_LIMIT: data[f"{ATTR_API_NO2}_{SUFFIX_LIMIT}"],
            ATTR_PERCENT: round(data[f"{ATTR_API_NO2}_{SUFFIX_PERCENT}"]),
        },
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_SO2,
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        attrs=lambda data: {
            ATTR_LIMIT: data[f"{ATTR_API_SO2}_{SUFFIX_LIMIT}"],
            ATTR_PERCENT: round(data[f"{ATTR_API_SO2}_{SUFFIX_PERCENT}"]),
        },
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_O3,
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        attrs=lambda data: {
            ATTR_LIMIT: data[f"{ATTR_API_O3}_{SUFFIX_LIMIT}"],
            ATTR_PERCENT: round(data[f"{ATTR_API_O3}_{SUFFIX_PERCENT}"]),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Airly sensor entities based on a config entry."""
    name = entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for description in SENSOR_TYPES:
        # When we use the nearest method, we are not sure which sensors are available
        if coordinator.data.get(description.key):
            sensors.append(AirlySensor(coordinator, name, description))

    async_add_entities(sensors, False)


class AirlySensor(CoordinatorEntity[AirlyDataUpdateCoordinator], SensorEntity):
    """Define an Airly sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: AirlySensorEntityDescription

    def __init__(
        self,
        coordinator: AirlyDataUpdateCoordinator,
        name: str,
        description: AirlySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{coordinator.latitude}-{coordinator.longitude}")},
            manufacturer=MANUFACTURER,
            name=name,
            configuration_url=URL.format(
                latitude=coordinator.latitude, longitude=coordinator.longitude
            ),
        )
        self._attr_unique_id = (
            f"{coordinator.latitude}-{coordinator.longitude}-{description.key}".lower()
        )
        self._attr_native_value = coordinator.data[description.key]
        self._attr_extra_state_attributes = description.attrs(coordinator.data)
        self.entity_description = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data[self.entity_description.key]
        self._attr_extra_state_attributes = self.entity_description.attrs(
            self.coordinator.data
        )
        self.async_write_ha_state()
