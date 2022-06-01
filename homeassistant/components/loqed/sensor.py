"""Loqed sensor entities."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LoqedDataCoordinator
from .const import CONF_COORDINATOR, CONF_LOCK, DOMAIN

SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        name="Loqed battery status",
        key="battery_percentage",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
    ),
    SensorEntityDescription(
        name="Loqed wifi signal strength",
        key="wifi_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
        icon="mdi:signal",
    ),
    SensorEntityDescription(
        name="Loqed bluetooth signal strength",
        key="ble_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        entity_registry_enabled_default=False,
        icon="mdi:signal",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Loqed sensor."""
    coordinator: LoqedDataCoordinator = hass.data[DOMAIN][entry.entry_id][
        CONF_COORDINATOR
    ]
    mac_address = hass.data[DOMAIN][entry.entry_id][CONF_LOCK].id

    entities = [LoqedSensor(mac_address, sensor, coordinator) for sensor in SENSORS]
    async_add_entities(entities)


class LoqedSensor(CoordinatorEntity[LoqedDataCoordinator], SensorEntity):
    """Class representing a LoqedSensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        mac_address: str,
        sensor_description: SensorEntityDescription,
        coordinator: LoqedDataCoordinator,
    ) -> None:
        """Initialize the loqed sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            name="Loqed instance",
        )
        self.entity_description = sensor_description
        self._attr_unique_id = f"{sensor_description.key}-{mac_address}"
        self._attr_native_unit_of_measurement = (
            sensor_description.native_unit_of_measurement
        )

        self._attr_native_value = coordinator.data[sensor_description.key]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        key = self.entity_description.key

        if key in self.coordinator.data:
            self._attr_native_value = self.coordinator.data[key]
            self.async_write_ha_state()
