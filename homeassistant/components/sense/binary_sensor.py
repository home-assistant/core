"""Support for monitoring a Sense energy sensor device."""

import logging

from sense_energy.sense_api import SenseDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SenseConfigEntry
from .const import DOMAIN
from .coordinator import SenseRealtimeCoordinator
from .entity import SenseDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SenseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sense binary sensor."""
    sense_monitor_id = config_entry.runtime_data.data.sense_monitor_id
    realtime_coordinator = config_entry.runtime_data.rt

    devices = [
        SenseBinarySensor(device, realtime_coordinator, sense_monitor_id)
        for device in config_entry.runtime_data.data.devices
    ]

    await _migrate_old_unique_ids(hass, devices)

    async_add_entities(devices)


class SenseBinarySensor(SenseDeviceEntity, BinarySensorEntity):
    """Implementation of a Sense energy device binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(
        self,
        device: SenseDevice,
        coordinator: SenseRealtimeCoordinator,
        sense_monitor_id: str,
    ) -> None:
        """Initialize the Sense binary sensor."""
        super().__init__(device, coordinator, sense_monitor_id, device.id)
        self._id = device.id

    @property
    def old_unique_id(self) -> str:
        """Return the old not so unique id of the binary sensor."""
        return self._id

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.is_on


async def _migrate_old_unique_ids(
    hass: HomeAssistant, devices: list[SenseBinarySensor]
) -> None:
    registry = er.async_get(hass)
    for device in devices:
        # Migration of old not so unique ids
        old_entity_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, device.old_unique_id
        )
        updated_id = device.unique_id
        if old_entity_id is not None and updated_id is not None:
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                device.old_unique_id,
                device.unique_id,
            )
            registry.async_update_entity(old_entity_id, new_unique_id=updated_id)
