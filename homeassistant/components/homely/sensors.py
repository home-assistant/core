"""Sensors provided by Homely."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homelypy.devices import SingleLocation, WindowSensor
from homelypy.homely import Homely

_LOGGER = logging.getLogger(__name__)


class PollingDataCoordinator(DataUpdateCoordinator):
    """Homely polling data coordinator."""

    def __init__(
        self, hass: HomeAssistant, homely: Homely, location: SingleLocation
    ) -> None:
        """Initialise homely connection."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Homely {location.name}",
            update_interval=timedelta(minutes=5),
        )
        self.homely = homely
        self.location = location
        self.added_sensors: set[str] = set()

    async def _async_update_data(self) -> None:
        self.location = await self.hass.async_add_executor_job(
            self.homely.get_location, self.location.location_id
        )
        for device in self.location.devices:
            if device.id not in self.added_sensors:
                self.added_sensors.add(device.id)


class WindowSensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Homely window sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, coordinator, device_id):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.device_id = device_id

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device: WindowSensor = next(
            filter(
                lambda device: (device.id == self.device_id),
                self.coordinator.location.devices,
            )
        )
        self._attr_is_on = device.alarm.alarm
        self.async_write_ha_state()
