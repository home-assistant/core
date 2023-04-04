"""Support for SwitchBot sensors."""
from __future__ import annotations

from homeassistant.components.bluetooth import async_last_service_info
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 0

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "rssi": SensorEntityDescription(
        key="rssi",
        translation_key="bluetooth_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "wifi_rssi": SensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "lightLevel": SensorEntityDescription(
        key="lightLevel",
        translation_key="light_level",
        native_unit_of_measurement="Level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    "temperature": SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "power": SensorEntityDescription(
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbot sensor based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        SwitchBotSensor(coordinator, sensor)
        for sensor in coordinator.device.parsed_data
        if sensor in SENSOR_TYPES
    ]
    entities.append(SwitchbotRSSISensor(coordinator, "rssi"))
    async_add_entities(entities)


class SwitchBotSensor(SwitchbotEntity, SensorEntity):
    """Representation of a Switchbot sensor."""

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        sensor: str,
    ) -> None:
        """Initialize the Switchbot sensor."""
        super().__init__(coordinator)
        self._sensor = sensor
        self._attr_unique_id = f"{coordinator.base_unique_id}-{sensor}"
        self.entity_description = SENSOR_TYPES[sensor]

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.parsed_data[self._sensor]


class SwitchbotRSSISensor(SwitchBotSensor):
    """Representation of a Switchbot RSSI sensor."""

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        # Switchbot supports both connectable and non-connectable devices
        # so we need to request the rssi value based on the connectable instead
        # of the nearest scanner since that is the RSSI that matters for controlling
        # the device.
        if service_info := async_last_service_info(
            self.hass, self._address, self.coordinator.connectable
        ):
            return service_info.rssi
        return None
