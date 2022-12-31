"""Sensors provided by Homely."""
from datetime import timedelta
import logging

from httpcore import ConnectTimeout
from httpx import HTTPError

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homelypy.devices import SingleLocation, WindowSensor
from homelypy.homely import ConnectionFailedException, Homely

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Plate Relays as switch based on a config entry."""
    homely = hass.data[DOMAIN][entry.entry_id]
    location_id = entry.data["location_id"]

    try:
        location = await hass.async_add_executor_job(homely.get_location, location_id)
    except (ConnectionFailedException, ConnectTimeout, HTTPError) as ex:
        raise PlatformNotReady(f"Unable to connect to Homely: {ex}") from ex

    coordinator = PollingDataCoordinator(hass, homely, location)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for device in coordinator.location.devices:
        if device.id not in coordinator.added_sensors:
            coordinator.added_sensors.add(device.id)
            print(f"Reviewing device {device}")
            if isinstance(device, WindowSensor):
                print("This is a Window sensor")
                entities.append(WindowSensorEntity(coordinator, device))
    async_add_entities(entities)


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


class WindowSensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Homely window sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, coordinator, device: WindowSensor):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = device.name
        self._attr_is_on = device.alarm.alarm
        self._attr_unique_id = f"{DOMAIN}_{device.id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},  # type: ignore[arg-type]
            name=f"{self.device.location} - {self.device.name}",
            manufacturer="",
            model=self.device.model_name,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device: WindowSensor = next(
            filter(
                lambda device: (device.id == self.device.id),
                self.coordinator.location.devices,
            )
        )
        self._attr_is_on = device.alarm.alarm
        self.async_write_ha_state()
