"""LD2410 BLE integration sensor platform."""


from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LD2410BLE, LD2410BLECoordinator
from .const import DOMAIN
from .models import LD2410BLEData

distance_description: Callable[
    [str, str], SensorEntityDescription
] = lambda key, name: SensorEntityDescription(
    key=key,
    device_class=SensorDeviceClass.DISTANCE,
    entity_registry_enabled_default=False,
    entity_registry_visible_default=True,
    has_entity_name=True,
    name=name,
    native_unit_of_measurement=UnitOfLength.CENTIMETERS,
)


MOVING_TARGET_DISTANCE_DESCRIPTION = distance_description(
    "moving_target_distance",
    "Moving Target Distance",
)
STATIC_TARGET_DISTANCE_DESCRIPTION = distance_description(
    "static_target_distance",
    "Static Target Distance",
)


energy_description: Callable[
    [str, str], SensorEntityDescription
] = lambda key, name: SensorEntityDescription(
    key=key,
    device_class=None,
    entity_registry_enabled_default=False,
    entity_registry_visible_default=True,
    has_entity_name=True,
    name=name,
    native_unit_of_measurement="Target Energy",
)


MOVING_TARGET_ENERGY_DESCRIPTION = energy_description(
    "moving_target_energy",
    "Moving Target Energy",
)
STATIC_TARGET_ENERGY_DESCRIPTION = energy_description(
    "static_target_energy",
    "Static Target Energy",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform for LD2410BLE."""
    data: LD2410BLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LD2410BLESensor(
                data.coordinator,
                data.device,
                entry.title,
                MOVING_TARGET_DISTANCE_DESCRIPTION,
            ),
            LD2410BLESensor(
                data.coordinator,
                data.device,
                entry.title,
                STATIC_TARGET_DISTANCE_DESCRIPTION,
            ),
            LD2410BLESensor(
                data.coordinator,
                data.device,
                entry.title,
                MOVING_TARGET_ENERGY_DESCRIPTION,
            ),
            LD2410BLESensor(
                data.coordinator,
                data.device,
                entry.title,
                STATIC_TARGET_ENERGY_DESCRIPTION,
            ),
        ]
    )


class LD2410BLESensor(CoordinatorEntity, SensorEntity):
    """Moving/static target distance sensor for LD2410BLE."""

    def __init__(
        self,
        coordinator: LD2410BLECoordinator,
        device: LD2410BLE,
        name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._device = device
        self._key = description.key
        self.entity_description = description
        self._attr_unique_id = f"{device.address}_{self._key}"
        self._attr_device_info = DeviceInfo(
            name=name,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )
        self._attr_native_value = getattr(self._device, self._key)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = getattr(self._device, self._key)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Unavailable if coordinator isn't connected."""
        return self._coordinator.connected and super().available
