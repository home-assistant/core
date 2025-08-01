"""Support for the Airzone sensors."""

from __future__ import annotations

import logging
from typing import Any, Final

from airzone_mqtt.const import (
    AZD_HUMIDITY,
    AZD_MODE,
    AZD_SETPOINT,
    AZD_SETPOINT_MAX,
    AZD_SETPOINT_MIN,
    AZD_UNITS,
    AZD_ZONE_WORK_TEMP,
    AZD_ZONES,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TEMP_UNIT_LIB_TO_HASS
from .coordinator import AirzoneMqttConfigEntry, AirzoneUpdateCoordinator
from .entity import AirzoneEntity, AirzoneZoneEntity

_LOGGER = logging.getLogger(__name__)

ZONE_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key=AZD_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_MODE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="hvac_mode",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_SETPOINT,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="hvac_setpoint",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_SETPOINT_MAX,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="hvac_setpoint_max",
    ),
    SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_SETPOINT_MIN,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="hvac_setpoint_min",
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=AZD_ZONE_WORK_TEMP,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirzoneMqttConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Airzone sensors from a config_entry."""
    coordinator = entry.runtime_data

    added_zones: set[str] = set()

    def _async_entity_listener() -> None:
        """Handle additions of sensors."""

        entities: list[AirzoneSensor] = []

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

    async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class AirzoneSensor(AirzoneEntity, SensorEntity):
    """Define an Airzone sensor."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = self.get_airzone_value(self.entity_description.key)


class AirzoneZoneSensor(AirzoneZoneEntity, AirzoneSensor):
    """Define an Airzone Zone sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        description: SensorEntityDescription,
        entry: ConfigEntry,
        airzone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, airzone_id, zone_data)

        self._attr_unique_id = f"{self._attr_unique_id}_{airzone_id}_{description.key}"
        self.entity_description = description

        if description.key == AZD_ZONE_WORK_TEMP:
            self._attr_native_unit_of_measurement = TEMP_UNIT_LIB_TO_HASS.get(
                self.get_airzone_value(AZD_UNITS)
            )

        self._async_update_attrs()
