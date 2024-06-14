"""Sensoterra devices."""

from __future__ import annotations

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONFIGURATION_URL, DOMAIN
from .coordinator import SensoterraCoordinator, SensoterraSensor

SENSORS: dict[str, SensorEntityDescription] = {
    "MOISTURE": SensorEntityDescription(
        key="MOISTURE",
        has_entity_name=True,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        translation_key="soil_moisture_at_cm",
    ),
    "SI": SensorEntityDescription(
        key="SI",
        has_entity_name=True,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        name="SI @ {depth} cm",
    ),
    "TEMPERATURE": SensorEntityDescription(
        key="TEMPERATURE",
        has_entity_name=True,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "BATTERY": SensorEntityDescription(
        key="BATTERY",
        has_entity_name=True,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "RSSI": SensorEntityDescription(
        key="RSSI",
        has_entity_name=True,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "LASTSEEN": SensorEntityDescription(
        key="LASTSEEN",
        has_entity_name=True,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="last_seen",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
) -> None:
    """Set up Sensoterra sensor."""

    coordinator: SensoterraCoordinator = entry.runtime_data

    def _add_devices(devices: dict[str, SensoterraSensor]) -> None:
        async_add_devices(
            [
                SensoterraEntity(coordinator, sensor)
                for sensor in devices.values()
                if sensor.type in SENSORS
            ]
        )

    coordinator.add_devices_callback = _add_devices

    _add_devices(coordinator.data)


class SensoterraEntity(CoordinatorEntity[SensoterraCoordinator], SensorEntity):
    """Sensoterra sensor like a soil moisture or temperature sensor."""

    def __init__(
        self,
        coordinator: SensoterraCoordinator,
        sensor: SensoterraSensor,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, context=sensor.id)

        self.sensor_id = sensor.id
        self._attr_unique_id = sensor.id

        self.entity_description = SENSORS[sensor.type]

        # Make sure {depth} placeholders gets substituted.
        self._attr_translation_placeholders = {"depth": str(sensor.depth)}
        if isinstance(self.entity_description.name, str):
            self._attr_name = self.entity_description.name.format(depth=sensor.depth)

        # Add soil type to certain sensors.
        if sensor.soil is not None and sensor.type in ["MOISTURE", "SI"]:
            self._attr_extra_state_attributes = {"soil_type": sensor.soil}

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor.serial)},
            name=sensor.name,
            model=sensor.sku,
            manufacturer="Sensoterra",
            serial_number=sensor.serial,
            suggested_area=sensor.location,
            configuration_url=CONFIGURATION_URL,
        )

        if sensor.value is not None:
            self._attr_native_value = sensor.value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        sensors: dict[str, SensoterraSensor] = self.coordinator.data
        for sensor in sensors.values():
            if sensor.id == self.sensor_id:
                if sensor.value is not None:
                    self._attr_native_value = sensor.value
                    self.async_write_ha_state()
