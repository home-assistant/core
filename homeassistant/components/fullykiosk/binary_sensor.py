"""Fully Kiosk Browser sensor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(key="kioskMode", name="Kiosk Mode"),
    BinarySensorEntityDescription(
        key="plugged",
        name="Plugged In",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    BinarySensorEntityDescription(
        key="isDeviceAdmin",
        name="Device Admin",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser sensor."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [
        FullyBinarySensor(coordinator, sensor)
        for sensor in SENSOR_TYPES
        if sensor.key in coordinator.data
    ]

    async_add_entities(sensors, False)


class FullyBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Fully Kiosk Browser binary sensor."""

    def __init__(self, coordinator, sensor):
        """Initialize the binary sensor."""
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
    def is_on(self) -> bool | None:
        """Return if the binary sensor is on."""
        if self.coordinator.data:
            return self.coordinator.data[self._sensor]
        return None

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update Fully Kiosk Browser entity."""
        await self.coordinator.async_request_refresh()
