"""Support for Imou binary sensor entities."""

from typing import override

from pyimouapi.const import PARAM_STATE
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PARAM_DOOR_CONTACT_STATUS, imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 0

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=PARAM_DOOR_CONTACT_STATUS,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
)


def _iter_binary_sensors(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[BinarySensorEntityDescription, ImouHaDevice]]:
    """Return (description, device) pairs for supported binary sensors."""
    return [
        (description, device)
        for device in coordinator.devices
        for description in BINARY_SENSOR_TYPES
        if description.key in device.binary_sensors
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou binary sensor entities."""
    coordinator = entry.runtime_data

    def _add_binary_sensors(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouBinarySensor(coordinator, description, device)
            for description, device in _iter_binary_sensors(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    entry.async_on_unload(coordinator.register_new_device_callback(_add_binary_sensors))
    _add_binary_sensors(coordinator.devices)


class ImouBinarySensor(ImouEntity, BinarySensorEntity):
    """Imou binary sensor entity."""

    entity_description: BinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when the sensor is active."""
        return self.device.binary_sensors[self._entity_type][PARAM_STATE]
