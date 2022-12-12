"""LD2410 BLE integration light platform."""

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .models import LD2410BLEData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform for LD2410BLE."""
    data: LD2410BLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IsMovingSensor(data.coordinator, data.device, entry.title)])
    async_add_entities([IsStaticSensor(data.coordinator, data.device, entry.title)])


class IsMovingSensor(CoordinatorEntity, BinarySensorEntity):
    """Moving sensor for LD2410BLE."""

    def __init__(self, coordinator, device, name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._value = False

        self._device = device
        self._attr_available = True
        self._attr_unique_id = device.address + "_is_moving"
        self._attr_device_info = DeviceInfo(
            name=name,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._value = self._device.is_moving
        self.async_write_ha_state()

    @property
    def should_poll(self):
        """Don't poll."""
        return False

    @property
    def is_on(self):
        """Is motion detected."""
        return self._value

    @property
    def device_class(self):
        """Motion."""
        return "motion"


class IsStaticSensor(CoordinatorEntity, BinarySensorEntity):
    """Static sensor for LD2410BLE."""

    def __init__(self, coordinator, device, name):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._value = False

        self._device = device
        self._attr_unique_id = device.address + "_is_static"
        self._attr_device_info = DeviceInfo(
            name=name,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )

    @callback
    def _handle_coordinator_update(self, *args: Any) -> None:
        """Handle updated data from the coordinator."""
        self._value = self._device.is_static
        self.async_write_ha_state()

    @property
    def should_poll(self):
        """Don't poll."""
        return False

    @property
    def is_on(self):
        """Is occupancy detected."""
        return self._value

    @property
    def device_class(self):
        """Occupancy."""
        return "occupancy"
