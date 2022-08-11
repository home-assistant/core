"""Fully Kiosk Browser sensor."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DATA_MEGABYTES, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="batteryLevel",
        name="Battery Level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(key="screenOrientation", name="Screen Orientation"),
    SensorEntityDescription(
        key="foregroundApp",
        name="Foreground App",
    ),
    SensorEntityDescription(
        key="lastAppStart",
        name="Last App Start",
    ),
    SensorEntityDescription(key="currentPage", name="Current Page"),
    SensorEntityDescription(
        key="wifiSignalLevel",
        name="WiFi Signal Level",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    ),
    SensorEntityDescription(
        key="internalStorageFreeSpace",
        name="Internal Storage Free Space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="internalStorageTotalSpace",
        name="Internal Storage Total Space",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="ramFreeMemory",
        name="RAM Free Memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
    SensorEntityDescription(
        key="ramTotalMemory",
        name="RAM Total Memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DATA_MEGABYTES,
    ),
)

STORAGE_SENSORS = [
    "internalStorageFreeSpace",
    "internalStorageTotalSpace",
    "ramFreeMemory",
    "ramTotalMemory",
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser sensor."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [
        FullySensor(coordinator, sensor)
        for sensor in SENSOR_TYPES
        if sensor.key in coordinator.data
    ]

    async_add_entities(sensors, False)


class FullySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Fully Kiosk Browser sensor."""

    def __init__(self, coordinator, sensor: SensorEntityDescription):
        """Initialize the sensor entity."""
        self.entity_description = sensor
        self._sensor = sensor.key
        self.coordinator = coordinator

        self._attr_name = f"{coordinator.data['deviceName']} {sensor.name}"
        self._attr_unique_id = f"{coordinator.data['deviceID']}-{sensor.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.coordinator.data["deviceID"])},
            "name": self.coordinator.data["deviceName"],
            "manufacturer": self.coordinator.data["deviceManufacturer"],
            "model": self.coordinator.data["deviceModel"],
            "sw_version": self.coordinator.data["appVersionName"],
            "configuration_url": f"http://{self.coordinator.data['ip4']}:2323",
        }

        super().__init__(coordinator)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        if self._sensor in STORAGE_SENSORS:
            return round(self.coordinator.data[self._sensor] * 0.000001, 1)

        return self.coordinator.data.get(self._sensor)

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update Fully Kiosk Browser entity."""
        await self.coordinator.async_request_refresh()
