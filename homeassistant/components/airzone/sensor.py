"""Support for the Airzone sensors."""

from typing import Any, Final, override

from aioairzone.const import (
    AZD_ECO_ADAPT,
    AZD_ENERGY,
    AZD_HOT_WATER,
    AZD_HUMIDITY,
    AZD_SYSTEMS,
    AZD_TEMP,
    AZD_TEMP_UNIT,
    AZD_THERMOSTAT_BATTERY,
    AZD_THERMOSTAT_SIGNAL,
    AZD_WEBSERVER,
    AZD_WIFI_CHANNEL,
    AZD_WIFI_QUALITY,
    AZD_WIFI_RSSI,
    AZD_ZONES,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TEMP_UNIT_LIB_TO_HASS
from .coordinator import AirzoneConfigEntry, AirzoneUpdateCoordinator
from .entity import (
    AirzoneEntity,
    AirzoneHotWaterEntity,
    AirzoneSystemEntity,
    AirzoneWebServerEntity,
    AirzoneZoneEntity,
)

HOT_WATER_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=AZD_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SYSTEM_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        key=AZD_ECO_ADAPT,
        options=["off", "manual", "a", "a_p", "a_pp"],
        translation_key="eco_adapt",
    ),
    # The aioairzone AZD_ENERGY value is the clamp meter instantaneous power
    # reading (in watts), hence the power device class despite the name.
    SensorEntityDescription(
        device_class=SensorDeviceClass.POWER,
        key=AZD_ENERGY,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

WEBSERVER_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_WIFI_RSSI,
        translation_key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_WIFI_CHANNEL,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="wifi_channel",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_WIFI_QUALITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="wifi_quality",
    ),
)

ZONE_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
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
        key=AZD_THERMOSTAT_SIGNAL,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="thermostat_signal",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Airzone sensors from a config_entry."""
    coordinator = entry.runtime_data

    added_systems: set[str] = set()
    added_zones: set[str] = set()

    def _async_entity_listener() -> None:
        """Handle additions of sensors."""

        entities: list[AirzoneSensor] = []

        systems_data = coordinator.data.get(AZD_SYSTEMS, {})
        received_systems = set(systems_data)
        new_systems = received_systems - added_systems
        if new_systems:
            entities.extend(
                AirzoneSystemSensor(
                    coordinator,
                    description,
                    entry,
                    system_id,
                    systems_data.get(system_id),
                )
                for system_id in new_systems
                for description in SYSTEM_SENSOR_TYPES
                if description.key in systems_data.get(system_id)
            )
            added_systems.update(new_systems)

        zones_data = coordinator.data.get(AZD_ZONES, {})
        received_zones = set(zones_data)
        new_zones = received_zones - added_zones
        if new_zones:
            entities.extend(
                AirzoneZoneSensor(
                    coordinator,
                    description,
                    entry,
                    system_zone_id,
                    zones_data.get(system_zone_id),
                )
                for system_zone_id in new_zones
                for description in ZONE_SENSOR_TYPES
                if description.key in zones_data.get(system_zone_id)
            )
            added_zones.update(new_zones)

        async_add_entities(entities)

    entities: list[AirzoneSensor] = []

    if AZD_HOT_WATER in coordinator.data:
        entities.extend(
            AirzoneHotWaterSensor(
                coordinator,
                description,
                entry,
            )
            for description in HOT_WATER_SENSOR_TYPES
            if description.key in coordinator.data[AZD_HOT_WATER]
        )

    if AZD_WEBSERVER in coordinator.data:
        entities.extend(
            AirzoneWebServerSensor(
                coordinator,
                description,
                entry,
            )
            for description in WEBSERVER_SENSOR_TYPES
            if description.key in coordinator.data[AZD_WEBSERVER]
        )

    async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class AirzoneSensor(AirzoneEntity, SensorEntity):
    """Define an Airzone sensor."""

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = self.get_airzone_value(self.entity_description.key)


class AirzoneHotWaterSensor(AirzoneHotWaterEntity, AirzoneSensor):
    """Define an Airzone Hot Water sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{self._attr_unique_id}_dhw_{description.key}"
        self.entity_description = description

        self._attr_native_unit_of_measurement = TEMP_UNIT_LIB_TO_HASS.get(
            self.get_airzone_value(AZD_TEMP_UNIT)
        )

        self._async_update_attrs()


class AirzoneWebServerSensor(AirzoneWebServerEntity, AirzoneSensor):
    """Define an Airzone WebServer sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._attr_unique_id}_ws_{description.key}"
        self.entity_description = description
        self._async_update_attrs()


class AirzoneSystemSensor(AirzoneSystemEntity, AirzoneSensor):
    """Define an Airzone System sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
        system_id: str,
        system_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, system_data)

        self._attr_unique_id = f"{self._attr_unique_id}_{system_id}_{description.key}"
        self.entity_description = description

        self._async_update_attrs()


class AirzoneZoneSensor(AirzoneZoneEntity, AirzoneSensor):
    """Define an Airzone Zone sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, system_zone_id, zone_data)

        self._attr_unique_id = (
            f"{self._attr_unique_id}_{system_zone_id}_{description.key}"
        )
        self.entity_description = description

        if description.key == AZD_TEMP:
            self._attr_native_unit_of_measurement = TEMP_UNIT_LIB_TO_HASS.get(
                self.get_airzone_value(AZD_TEMP_UNIT)
            )

        self._async_update_attrs()
