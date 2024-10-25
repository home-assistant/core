"""Support for monitoring a Sense energy sensor device."""

import logging

from sense_energy.sense_api import SenseDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SenseConfigEntry
from .const import ATTRIBUTION, DOMAIN, MDI_ICONS
from .coordinator import SenseRealtimeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SenseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sense binary sensor."""
    sense_monitor_id = config_entry.runtime_data.data.sense_monitor_id
    realtime_coordinator = config_entry.runtime_data.rt

    devices = [
        SenseBinarySensor(device, sense_monitor_id, realtime_coordinator)
        for device in config_entry.runtime_data.data.devices
    ]

    await _migrate_old_unique_ids(hass, devices)

    async_add_entities(devices)


def sense_to_mdi(sense_icon: str) -> str:
    """Convert sense icon to mdi icon."""
    return f"mdi:{MDI_ICONS.get(sense_icon, "power-plug")}"


class SenseBinarySensor(
    CoordinatorEntity[SenseRealtimeCoordinator], BinarySensorEntity
):
    """Implementation of a Sense energy device binary sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(
        self,
        device: SenseDevice,
        sense_monitor_id: str,
        coordinator: SenseRealtimeCoordinator,
    ) -> None:
        """Initialize the Sense binary sensor."""
        super().__init__(coordinator)
        self._attr_name = device.name
        self._id = device.id
        self._attr_unique_id = f"{sense_monitor_id}-{self._id}"
        self._attr_icon = sense_to_mdi(device.icon)
        self._device = device

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
