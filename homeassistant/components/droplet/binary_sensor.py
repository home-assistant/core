"""Support for Droplet binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from pydroplet.droplet import Droplet

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_HIGH_FLOW, KEY_UNUSUAL_FLOW
from .coordinator import DropletConfigEntry, DropletDataCoordinator

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class DropletBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Droplet binary sensor entity."""

    value_fn: Callable[[Droplet], bool | None]


BINARY_SENSORS: list[DropletBinarySensorEntityDescription] = [
    DropletBinarySensorEntityDescription(
        key=KEY_UNUSUAL_FLOW,
        translation_key=KEY_UNUSUAL_FLOW,
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda device: device.get_low_leak(),
    ),
    DropletBinarySensorEntityDescription(
        key=KEY_HIGH_FLOW,
        translation_key=KEY_HIGH_FLOW,
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda device: device.get_high_leak(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DropletConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Droplet binary sensors from config entry."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        [DropletBinarySensor(coordinator, sensor) for sensor in BINARY_SENSORS]
    )


class DropletBinarySensor(
    CoordinatorEntity[DropletDataCoordinator], BinarySensorEntity
):
    """Representation of a Droplet binary sensor."""

    entity_description: DropletBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DropletDataCoordinator,
        entity_description: DropletBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        unique_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.unique_id)},
            manufacturer=self.coordinator.droplet.get_manufacturer(),
            model=self.coordinator.droplet.get_model(),
            sw_version=self.coordinator.droplet.get_fw_version(),
            serial_number=self.coordinator.droplet.get_sn(),
        )

    @property
    def available(self) -> bool:
        """Get Droplet's availability."""
        return self.coordinator.get_availability()

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.droplet)
