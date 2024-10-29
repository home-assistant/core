"""Support for the Airzone Cloud sensors."""

from __future__ import annotations

from typing import Any, Final

from aioairzone_cloud.const import (
    AZD_AIDOOS,
    AZD_AQ_INDEX,
    AZD_AQ_PM_1,
    AZD_AQ_PM_2P5,
    AZD_AQ_PM_10,
    AZD_CPU_USAGE,
    AZD_HUMIDITY,
    AZD_INDOOR_EXCHANGER_TEMP,
    AZD_INDOOR_RETURN_TEMP,
    AZD_INDOOR_WORK_TEMP,
    AZD_MEMORY_FREE,
    AZD_OUTDOOR_CONDENSER_PRESS,
    AZD_OUTDOOR_DISCHARGE_TEMP,
    AZD_OUTDOOR_ELECTRIC_CURRENT,
    AZD_OUTDOOR_EVAPORATOR_PRESS,
    AZD_OUTDOOR_EXCHANGER_TEMP,
    AZD_OUTDOOR_TEMP,
    AZD_TEMP,
    AZD_THERMOSTAT_BATTERY,
    AZD_THERMOSTAT_COVERAGE,
    AZD_WEBSERVERS,
    AZD_WIFI_RSSI,
    AZD_ZONES,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfInformation,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneCloudConfigEntry
from .coordinator import AirzoneUpdateCoordinator
from .entity import (
    AirzoneAidooEntity,
    AirzoneEntity,
    AirzoneWebServerEntity,
    AirzoneZoneEntity,
)

AIDOO_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_INDOOR_EXCHANGER_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="indoor_exchanger_temp",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_INDOOR_RETURN_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="indoor_return_temp",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_INDOOR_WORK_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="indoor_work_temp",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_OUTDOOR_CONDENSER_PRESS,
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outdoor_condenser_press",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_OUTDOOR_DISCHARGE_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outdoor_discharge_temp",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_OUTDOOR_ELECTRIC_CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outdoor_electric_current",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_OUTDOOR_EVAPORATOR_PRESS,
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outdoor_evaporator_press",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_OUTDOOR_EXCHANGER_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outdoor_exchanger_temp",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_OUTDOOR_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="outdoor_temp",
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=AZD_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

WEBSERVER_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_CPU_USAGE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="cpu_usage",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_MEMORY_FREE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="free_memory",
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_WIFI_RSSI,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ZONE_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.AQI,
        key=AZD_AQ_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.PM1,
        key=AZD_AQ_PM_1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.PM25,
        key=AZD_AQ_PM_2P5,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.PM10,
        key=AZD_AQ_PM_10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=AZD_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key=AZD_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.BATTERY,
        key=AZD_THERMOSTAT_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_THERMOSTAT_COVERAGE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="thermostat_coverage",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneCloudConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Airzone Cloud sensors from a config_entry."""
    coordinator = entry.runtime_data

    # Aidoos
    sensors: list[AirzoneSensor] = [
        AirzoneAidooSensor(
            coordinator,
            description,
            aidoo_id,
            aidoo_data,
        )
        for aidoo_id, aidoo_data in coordinator.data.get(AZD_AIDOOS, {}).items()
        for description in AIDOO_SENSOR_TYPES
        if description.key in aidoo_data
    ]

    # WebServers
    sensors.extend(
        AirzoneWebServerSensor(
            coordinator,
            description,
            ws_id,
            ws_data,
        )
        for ws_id, ws_data in coordinator.data.get(AZD_WEBSERVERS, {}).items()
        for description in WEBSERVER_SENSOR_TYPES
        if description.key in ws_data
    )

    # Zones
    sensors.extend(
        AirzoneZoneSensor(
            coordinator,
            description,
            zone_id,
            zone_data,
        )
        for zone_id, zone_data in coordinator.data.get(AZD_ZONES, {}).items()
        for description in ZONE_SENSOR_TYPES
        if description.key in zone_data
    )

    async_add_entities(sensors)


class AirzoneSensor(AirzoneEntity, SensorEntity):
    """Define an Airzone Cloud sensor."""

    @property
    def available(self) -> bool:
        """Return Airzone Cloud sensor availability."""
        return super().available and self.native_value is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = self.get_airzone_value(self.entity_description.key)


class AirzoneAidooSensor(AirzoneAidooEntity, AirzoneSensor):
    """Define an Airzone Cloud Aidoo sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        aidoo_id: str,
        aidoo_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, aidoo_id, aidoo_data)

        self._attr_unique_id = f"{aidoo_id}_{description.key}"
        self.entity_description = description

        self._async_update_attrs()


class AirzoneWebServerSensor(AirzoneWebServerEntity, AirzoneSensor):
    """Define an Airzone Cloud WebServer sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        ws_id: str,
        ws_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, ws_id, ws_data)

        self._attr_unique_id = f"{ws_id}_{description.key}"
        self.entity_description = description

        self._async_update_attrs()


class AirzoneZoneSensor(AirzoneZoneEntity, AirzoneSensor):
    """Define an Airzone Cloud Zone sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, zone_id, zone_data)

        self._attr_unique_id = f"{zone_id}_{description.key}"
        self.entity_description = description

        self._async_update_attrs()
