"""Support for the Airzone sensors."""
from __future__ import annotations

from typing import Any, Final

from aioairzone.const import (
    AZD_HUMIDITY,
    AZD_NAME,
    AZD_TEMP,
    AZD_TEMP_UNIT,
    AZD_WEBSERVER,
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
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TEMP_UNIT_LIB_TO_HASS
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneEntity, AirzoneWebServerEntity, AirzoneZoneEntity

WEBSERVER_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=AZD_WIFI_RSSI,
        name="RSSI",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ZONE_SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        device_class=SensorDeviceClass.TEMPERATURE,
        key=AZD_TEMP,
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        device_class=SensorDeviceClass.HUMIDITY,
        key=AZD_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Airzone sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[AirzoneSensor] = []

    if AZD_WEBSERVER in coordinator.data:
        ws_data = coordinator.data[AZD_WEBSERVER]
        for description in WEBSERVER_SENSOR_TYPES:
            if description.key in ws_data:
                sensors.append(
                    AirzoneWebServerSensor(
                        coordinator,
                        description,
                        entry,
                    )
                )

    for system_zone_id, zone_data in coordinator.data[AZD_ZONES].items():
        for description in ZONE_SENSOR_TYPES:
            if description.key in zone_data:
                sensors.append(
                    AirzoneZoneSensor(
                        coordinator,
                        description,
                        entry,
                        system_zone_id,
                        zone_data,
                    )
                )

    async_add_entities(sensors)


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
        self._attr_name = f"WebServer {description.name}"
        self._attr_unique_id = f"{self._attr_unique_id}_ws_{description.key}"
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

        self._attr_name = f"{zone_data[AZD_NAME]} {description.name}"
        self._attr_unique_id = (
            f"{self._attr_unique_id}_{system_zone_id}_{description.key}"
        )
        self.entity_description = description

        if description.key == AZD_TEMP:
            self._attr_native_unit_of_measurement = TEMP_UNIT_LIB_TO_HASS.get(
                self.get_airzone_value(AZD_TEMP_UNIT)
            )

        self._async_update_attrs()
