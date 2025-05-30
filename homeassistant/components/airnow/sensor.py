"""Support for the AirNow sensor service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dateutil import parser

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_TIME,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_API_AQI,
    ATTR_API_AQI_DESCRIPTION,
    ATTR_API_AQI_LEVEL,
    ATTR_API_O3,
    ATTR_API_PM10,
    ATTR_API_PM25,
    ATTR_API_REPORT_DATE,
    ATTR_API_REPORT_HOUR,
    ATTR_API_REPORT_TZ,
    ATTR_API_STATION,
    ATTR_API_STATION_LATITUDE,
    ATTR_API_STATION_LONGITUDE,
    DEFAULT_NAME,
    DOMAIN,
    US_TZ_OFFSETS,
)
from .coordinator import AirNowConfigEntry, AirNowDataUpdateCoordinator

ATTRIBUTION = "Data provided by AirNow"

PARALLEL_UPDATES = 1

ATTR_DESCR = "description"
ATTR_LEVEL = "level"
ATTR_STATION = "reporting_station"


@dataclass(frozen=True, kw_only=True)
class AirNowEntityDescription(SensorEntityDescription):
    """Describes Airnow sensor entity."""

    value_fn: Callable[[Any], StateType]
    extra_state_attributes_fn: Callable[[Any], dict[str, str]] | None


def station_extra_attrs(data: dict[str, Any]) -> dict[str, Any]:
    """Process extra attributes for station location (if available)."""
    if ATTR_API_STATION in data:
        return {
            "lat": data.get(ATTR_API_STATION_LATITUDE),
            "long": data.get(ATTR_API_STATION_LONGITUDE),
        }
    return {}


def aqi_extra_attrs(data: dict[str, Any]) -> dict[str, Any]:
    """Process extra attributes for main AQI sensor."""
    return {
        ATTR_DESCR: data[ATTR_API_AQI_DESCRIPTION],
        ATTR_LEVEL: data[ATTR_API_AQI_LEVEL],
        ATTR_TIME: parser.parse(
            f"{data[ATTR_API_REPORT_DATE]} {data[ATTR_API_REPORT_HOUR]}:00 {data[ATTR_API_REPORT_TZ]}",
            tzinfos=US_TZ_OFFSETS,
        ).isoformat(),
    }


SENSOR_TYPES: tuple[AirNowEntityDescription, ...] = (
    AirNowEntityDescription(
        key=ATTR_API_AQI,
        translation_key="aqi",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda data: data.get(ATTR_API_AQI),
        extra_state_attributes_fn=aqi_extra_attrs,
    ),
    AirNowEntityDescription(
        key=ATTR_API_PM10,
        translation_key="pm10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM10,
        value_fn=lambda data: data.get(ATTR_API_PM10),
        extra_state_attributes_fn=None,
    ),
    AirNowEntityDescription(
        key=ATTR_API_PM25,
        translation_key="pm25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM25,
        value_fn=lambda data: data.get(ATTR_API_PM25),
        extra_state_attributes_fn=None,
    ),
    AirNowEntityDescription(
        key=ATTR_API_O3,
        translation_key="o3",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get(ATTR_API_O3),
        extra_state_attributes_fn=None,
    ),
    AirNowEntityDescription(
        key=ATTR_API_STATION,
        translation_key="station",
        value_fn=lambda data: data.get(ATTR_API_STATION),
        extra_state_attributes_fn=station_extra_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirNowConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirNow sensor entities based on a config entry."""
    coordinator = config_entry.runtime_data

    entities = [AirNowSensor(coordinator, description) for description in SENSOR_TYPES]

    async_add_entities(entities, False)


class AirNowSensor(CoordinatorEntity[AirNowDataUpdateCoordinator], SensorEntity):
    """Define an AirNow sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    entity_description: AirNowEntityDescription

    def __init__(
        self,
        coordinator: AirNowDataUpdateCoordinator,
        description: AirNowEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        _device_id = f"{coordinator.latitude}-{coordinator.longitude}"

        self.entity_description = description
        self._attr_unique_id = f"{_device_id}-{description.key.lower()}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, _device_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes."""
        if self.entity_description.extra_state_attributes_fn:
            return self.entity_description.extra_state_attributes_fn(
                self.coordinator.data
            )
        return None
