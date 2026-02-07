"""Creates the sensor entities for Google Air Quality."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from google_air_quality_api.model import AirQualityCurrentConditionsData, Index

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GoogleAirQualityConfigEntry
from .const import DOMAIN
from .coordinator import GoogleAirQualityUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


def _uaqi(data: AirQualityCurrentConditionsData) -> Index:
    if TYPE_CHECKING:
        assert data.indexes.uaqi is not None
    return data.indexes.uaqi


def _laqi(data: AirQualityCurrentConditionsData) -> Index:
    if TYPE_CHECKING:
        assert data.indexes.laqi is not None
    return data.indexes.laqi


@dataclass(frozen=True, kw_only=True)
class AirQualitySensorEntityDescription(SensorEntityDescription):
    """Describes Air Quality sensor entity."""

    exists_fn: Callable[[AirQualityCurrentConditionsData], bool] = lambda _: True
    options_fn: Callable[[AirQualityCurrentConditionsData], list[str] | None] = (
        lambda _: None
    )
    value_fn: Callable[[AirQualityCurrentConditionsData], StateType]
    native_unit_of_measurement_fn: Callable[
        [AirQualityCurrentConditionsData], str | None
    ] = lambda _: None
    translation_placeholders_fn: (
        Callable[[AirQualityCurrentConditionsData], dict[str, str]] | None
    ) = None


AIR_QUALITY_SENSOR_TYPES: tuple[AirQualitySensorEntityDescription, ...] = (
    AirQualitySensorEntityDescription(
        key="uaqi",
        translation_key="uaqi",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda x: _uaqi(x).aqi,
    ),
    AirQualitySensorEntityDescription(
        key="uaqi_category",
        translation_key="uaqi_category",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: _uaqi(x).category,
        options_fn=lambda x: _uaqi(x).category_options,
    ),
    AirQualitySensorEntityDescription(
        key="local_aqi",
        translation_key="local_aqi",
        exists_fn=lambda x: _laqi(x).aqi is not None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.AQI,
        value_fn=lambda x: _laqi(x).aqi,
        translation_placeholders_fn=lambda x: {"local_aqi": _laqi(x).display_name},
    ),
    AirQualitySensorEntityDescription(
        key="local_category",
        translation_key="local_category",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: _laqi(x).category,
        options_fn=lambda x: _laqi(x).category_options,
        translation_placeholders_fn=lambda x: {"local_aqi": _laqi(x).display_name},
    ),
    AirQualitySensorEntityDescription(
        key="uaqi_dominant_pollutant",
        translation_key="uaqi_dominant_pollutant",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: _uaqi(x).dominant_pollutant,
        options_fn=lambda x: _uaqi(x).pollutant_options,
    ),
    AirQualitySensorEntityDescription(
        key="local_dominant_pollutant",
        translation_key="local_dominant_pollutant",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda x: _laqi(x).dominant_pollutant,
        options_fn=lambda x: _laqi(x).pollutant_options,
        translation_placeholders_fn=lambda x: {"local_aqi": _laqi(x).display_name},
    ),
    AirQualitySensorEntityDescription(
        key="c6h6",
        translation_key="benzene",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement_fn=lambda x: x.pollutants.c6h6.concentration.units,
        value_fn=lambda x: x.pollutants.c6h6.concentration.value,
        exists_fn=lambda x: "c6h6" in {p.code for p in x.pollutants},
    ),
    AirQualitySensorEntityDescription(
        key="co",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement_fn=lambda x: x.pollutants.co.concentration.units,
        exists_fn=lambda x: "co" in {p.code for p in x.pollutants},
        value_fn=lambda x: x.pollutants.co.concentration.value,
        suggested_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    AirQualitySensorEntityDescription(
        key="nh3",
        translation_key="ammonia",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement_fn=lambda x: x.pollutants.nh3.concentration.units,
        value_fn=lambda x: x.pollutants.nh3.concentration.value,
        exists_fn=lambda x: "nh3" in {p.code for p in x.pollutants},
    ),
    AirQualitySensorEntityDescription(
        key="nmhc",
        translation_key="non_methane_hydrocarbons",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement_fn=lambda x: x.pollutants.nmhc.concentration.units,
        value_fn=lambda x: x.pollutants.nmhc.concentration.value,
        exists_fn=lambda x: "nmhc" in {p.code for p in x.pollutants},
    ),
    AirQualitySensorEntityDescription(
        key="no",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        native_unit_of_measurement_fn=lambda x: x.pollutants.no.concentration.units,
        value_fn=lambda x: x.pollutants.no.concentration.value,
        exists_fn=lambda x: "no" in {p.code for p in x.pollutants},
    ),
    AirQualitySensorEntityDescription(
        key="no2",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement_fn=lambda x: x.pollutants.no2.concentration.units,
        exists_fn=lambda x: "no2" in {p.code for p in x.pollutants},
        value_fn=lambda x: x.pollutants.no2.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="o3",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement_fn=lambda x: x.pollutants.o3.concentration.units,
        exists_fn=lambda x: "o3" in {p.code for p in x.pollutants},
        value_fn=lambda x: x.pollutants.o3.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="pm10",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement_fn=lambda x: x.pollutants.pm10.concentration.units,
        exists_fn=lambda x: "pm10" in {p.code for p in x.pollutants},
        value_fn=lambda x: x.pollutants.pm10.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="pm25",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement_fn=lambda x: x.pollutants.pm25.concentration.units,
        exists_fn=lambda x: "pm25" in {p.code for p in x.pollutants},
        value_fn=lambda x: x.pollutants.pm25.concentration.value,
    ),
    AirQualitySensorEntityDescription(
        key="so2",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement_fn=lambda x: x.pollutants.so2.concentration.units,
        exists_fn=lambda x: "so2" in {p.code for p in x.pollutants},
        value_fn=lambda x: x.pollutants.so2.concentration.value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleAirQualityConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinators = entry.runtime_data.subentries_runtime_data

    for subentry_id, subentry in entry.subentries.items():
        coordinator = coordinators[subentry_id]
        _LOGGER.debug("subentry.data: %s", subentry.data)
        async_add_entities(
            (
                AirQualitySensorEntity(coordinator, description, subentry_id, subentry)
                for description in AIR_QUALITY_SENSOR_TYPES
                if description.exists_fn(coordinator.data)
            ),
            config_subentry_id=subentry_id,
        )


class AirQualitySensorEntity(
    CoordinatorEntity[GoogleAirQualityUpdateCoordinator], SensorEntity
):
    """Defining the Air Quality Sensors with AirQualitySensorEntityDescription."""

    entity_description: AirQualitySensorEntityDescription
    _attr_attribution = "Data provided by Google Air Quality"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoogleAirQualityUpdateCoordinator,
        description: AirQualitySensorEntityDescription,
        subentry_id: str,
        subentry: ConfigSubentry,
    ) -> None:
        """Set up Air Quality Sensors."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}_{subentry.data[CONF_LATITUDE]}_{subentry.data[CONF_LONGITUDE]}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{self.coordinator.config_entry.entry_id}_{subentry_id}")
            },
            name=subentry.title,
            entry_type=DeviceEntryType.SERVICE,
        )
        if description.translation_placeholders_fn:
            self._attr_translation_placeholders = (
                description.translation_placeholders_fn(coordinator.data)
            )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return self.entity_description.options_fn(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement of the sensor."""
        return self.entity_description.native_unit_of_measurement_fn(
            self.coordinator.data
        )
