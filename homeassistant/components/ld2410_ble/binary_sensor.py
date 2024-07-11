"""LD2410 BLE integration binary sensor platform."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LD2410BLE, LD2410BLECoordinator
from .const import DOMAIN
from .models import LD2410BLEData

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="is_moving",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    BinarySensorEntityDescription(
        key="is_static",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform for LD2410BLE."""
    data: LD2410BLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LD2410BLEBinarySensor(data.coordinator, data.device, entry.title, description)
        for description in ENTITY_DESCRIPTIONS
    )


class LD2410BLEBinarySensor(
    CoordinatorEntity[LD2410BLECoordinator], BinarySensorEntity
):
    """Moving/static sensor for LD2410BLE."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LD2410BLECoordinator,
        device: LD2410BLE,
        name: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._key = description.key
        self._device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.address}_{self._key}"
        self._attr_device_info = DeviceInfo(
            name=name,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )
        self._attr_is_on = getattr(self._device, self._key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = getattr(self._device, self._key)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Unavailable if coordinator isn't connected."""
        return self._coordinator.connected and super().available
