"""Allpowers BLE integration binary sensor platform."""


from allpowers_ble import AllpowersBLE

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AllpowersBLECoordinator
from .models import AllpowersBLEData

ENTITY_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key="is_moving",
        device_class=BinarySensorDeviceClass.MOTION,
        has_entity_name=True,
        name="Motion",
    ),
    BinarySensorEntityDescription(
        key="is_static",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        has_entity_name=True,
        name="Occupancy",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform for AllpowersBLE."""
    data: AllpowersBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AllpowersBLEBinarySensor(
            data.coordinator, data.device, entry.title, description
        )
        for description in ENTITY_DESCRIPTIONS
    )


class AllpowersBLEBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Moving/static sensor for AllpowersBLE."""

    def __init__(
        self,
        coordinator: AllpowersBLECoordinator,
        device: AllpowersBLE,
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
        self._attr_device_info = dr.DeviceInfo(
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
