"""LD2410 BLE integration light platform."""


from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import LD2410BLE
from .const import DOMAIN
from .models import LD2410BLEData

ENTITY_DESCRIPTIONS = {
    "is_moving": BinarySensorEntityDescription(
        key="is_moving", device_class=BinarySensorDeviceClass.MOTION
    ),
    "is_static": BinarySensorEntityDescription(
        key="is_static", device_class=BinarySensorDeviceClass.PRESENCE
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform for LD2410BLE."""
    data: LD2410BLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LD2410BLEBinarySensor(
                data.coordinator, data.device, entry.title, "is_moving"
            ),
            LD2410BLEBinarySensor(
                data.coordinator, data.device, entry.title, "is_static"
            ),
        ]
    )


class LD2410BLEBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Moving/static sensor for LD2410BLE."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, device: LD2410BLE, name: str, key: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._key = key
        self._device = device
        self.entity_description = ENTITY_DESCRIPTIONS[key]
        self._attr_unique_id = device.address + f"_{key}"
        self._attr_device_info = DeviceInfo(
            name=name,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = getattr(self._device, self._key)
        self.async_write_ha_state()
