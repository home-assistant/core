"""Support for the Airly sensor service."""
from __future__ import annotations

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


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_API_CAQI,
        icon="mdi:air-filter",
        name=ATTR_API_CAQI,
        native_precision=0,
        native_unit_of_measurement="CAQI",
    ),
    SensorEntityDescription(
        key=ATTR_API_PM1,
        device_class=SensorDeviceClass.PM1,
        name=ATTR_API_PM1,
        native_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_PM25,
        device_class=SensorDeviceClass.PM25,
        name="PM2.5",
        native_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_PM10,
        device_class=SensorDeviceClass.PM10,
        name=ATTR_API_PM10,
        native_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        name=ATTR_API_HUMIDITY.capitalize(),
        native_precision=1,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        name=ATTR_API_PRESSURE.capitalize(),
        native_precision=0,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        name=ATTR_API_TEMPERATURE.capitalize(),
        native_precision=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_CO,
        name=ATTR_API_CO,
        native_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_NO2,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        name=ATTR_API_NO2,
        native_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_SO2,
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        name=ATTR_API_SO2,
        native_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_O3,
        device_class=SensorDeviceClass.OZONE,
        name=ATTR_API_O3,
        native_precision=0,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
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

    def __init__(
        self,
        coordinator: AirlyDataUpdateCoordinator,
        name: str,
        description: SensorEntityDescription,
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
        self._attrs: dict[str, Any] = {}
        self.entity_description = description

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.entity_description.key == ATTR_API_CAQI:
            self._attrs[ATTR_LEVEL] = self.coordinator.data[ATTR_API_CAQI_LEVEL]
            self._attrs[ATTR_ADVICE] = self.coordinator.data[ATTR_API_ADVICE]
            self._attrs[ATTR_DESCRIPTION] = self.coordinator.data[
                ATTR_API_CAQI_DESCRIPTION
            ]
        if self.entity_description.key == ATTR_API_PM25:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_PM25}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_PM25}_{SUFFIX_PERCENT}"]
            )
        if self.entity_description.key == ATTR_API_PM10:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_PM10}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_PM10}_{SUFFIX_PERCENT}"]
            )
        if self.entity_description.key == ATTR_API_CO:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_CO}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_CO}_{SUFFIX_PERCENT}"]
            )
        if self.entity_description.key == ATTR_API_NO2:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_NO2}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_NO2}_{SUFFIX_PERCENT}"]
            )
        if self.entity_description.key == ATTR_API_SO2:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_SO2}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_SO2}_{SUFFIX_PERCENT}"]
            )
        if self.entity_description.key == ATTR_API_O3:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_O3}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_O3}_{SUFFIX_PERCENT}"]
            )
        return self._attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data[self.entity_description.key]
        self.async_write_ha_state()
