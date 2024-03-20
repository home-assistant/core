"""Support for the World Air Quality Index service."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from typing import Any

from aiowaqi import WAQIAirQuality
from aiowaqi.models import Pollutant

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_TIME,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WAQIDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_DOMINENTPOL = "dominentpol"
ATTR_HUMIDITY = "humidity"
ATTR_NITROGEN_DIOXIDE = "nitrogen_dioxide"
ATTR_OZONE = "ozone"
ATTR_PM10 = "pm_10"
ATTR_PM2_5 = "pm_2_5"
ATTR_PRESSURE = "pressure"
ATTR_SULFUR_DIOXIDE = "sulfur_dioxide"


@dataclass(frozen=True, kw_only=True)
class WAQISensorEntityDescription(SensorEntityDescription):
    """Describes WAQI sensor entity."""

    available_fn: Callable[[WAQIAirQuality], bool]
    value_fn: Callable[[WAQIAirQuality], StateType]


SENSORS: list[WAQISensorEntityDescription] = [
    WAQISensorEntityDescription(
        key="air_quality",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.air_quality_index,
        available_fn=lambda _: True,
    ),
    WAQISensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.humidity,
        available_fn=lambda aq: aq.extended_air_quality.humidity is not None,
    ),
    WAQISensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.pressure,
        available_fn=lambda aq: aq.extended_air_quality.pressure is not None,
    ),
    WAQISensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.temperature,
        available_fn=lambda aq: aq.extended_air_quality.temperature is not None,
    ),
    WAQISensorEntityDescription(
        key="carbon_monoxide",
        translation_key="carbon_monoxide",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.carbon_monoxide,
        available_fn=lambda aq: aq.extended_air_quality.carbon_monoxide is not None,
    ),
    WAQISensorEntityDescription(
        key="nitrogen_dioxide",
        translation_key="nitrogen_dioxide",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.nitrogen_dioxide,
        available_fn=lambda aq: aq.extended_air_quality.nitrogen_dioxide is not None,
    ),
    WAQISensorEntityDescription(
        key="ozone",
        translation_key="ozone",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.ozone,
        available_fn=lambda aq: aq.extended_air_quality.ozone is not None,
    ),
    WAQISensorEntityDescription(
        key="sulphur_dioxide",
        translation_key="sulphur_dioxide",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.sulfur_dioxide,
        available_fn=lambda aq: aq.extended_air_quality.sulfur_dioxide is not None,
    ),
    WAQISensorEntityDescription(
        key="pm10",
        translation_key="pm10",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.pm10,
        available_fn=lambda aq: aq.extended_air_quality.pm10 is not None,
    ),
    WAQISensorEntityDescription(
        key="pm25",
        translation_key="pm25",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.pm25,
        available_fn=lambda aq: aq.extended_air_quality.pm25 is not None,
    ),
    WAQISensorEntityDescription(
        key="neph",
        translation_key="neph",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda aq: aq.extended_air_quality.nephelometry,
        available_fn=lambda aq: aq.extended_air_quality.nephelometry is not None,
        entity_registry_enabled_default=False,
    ),
    WAQISensorEntityDescription(
        key="dominant_pollutant",
        translation_key="dominant_pollutant",
        device_class=SensorDeviceClass.ENUM,
        options=[pollutant.value for pollutant in Pollutant],
        value_fn=lambda aq: aq.dominant_pollutant,
        available_fn=lambda _: True,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the WAQI sensor."""
    coordinator: WAQIDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WaqiSensor(coordinator, sensor)
            for sensor in SENSORS
            if sensor.available_fn(coordinator.data)
        ]
    )


class WaqiSensor(CoordinatorEntity[WAQIDataUpdateCoordinator], SensorEntity):
    """Implementation of a WAQI sensor."""

    _attr_has_entity_name = True
    entity_description: WAQISensorEntityDescription

    def __init__(
        self,
        coordinator: WAQIDataUpdateCoordinator,
        entity_description: WAQISensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.data.station_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.data.station_id))},
            name=coordinator.data.city.name,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_attribution = " and ".join(
            attribution.name for attribution in coordinator.data.attributions
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return old state attributes if the entity is AQI entity."""
        # These are deprecated and will be removed in 2024.5
        if self.entity_description.key != "air_quality":
            return None
        attrs: dict[str, Any] = {}
        attrs[ATTR_TIME] = self.coordinator.data.measured_at
        attrs[ATTR_DOMINENTPOL] = self.coordinator.data.dominant_pollutant

        iaqi = self.coordinator.data.extended_air_quality

        attribute = {
            ATTR_PM2_5: iaqi.pm25,
            ATTR_PM10: iaqi.pm10,
            ATTR_HUMIDITY: iaqi.humidity,
            ATTR_PRESSURE: iaqi.pressure,
            ATTR_TEMPERATURE: iaqi.temperature,
            ATTR_OZONE: iaqi.ozone,
            ATTR_NITROGEN_DIOXIDE: iaqi.nitrogen_dioxide,
            ATTR_SULFUR_DIOXIDE: iaqi.sulfur_dioxide,
        }
        res_attributes = {k: v for k, v in attribute.items() if v is not None}
        return {**attrs, **res_attributes}
