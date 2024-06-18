"""Support for monitoring a Sense energy sensor device."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SenseConfigEntry
from .const import ATTRIBUTION, DOMAIN, MDI_ICONS, SENSE_DEVICE_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SenseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sense binary sensor."""
    sense_monitor_id = config_entry.runtime_data.data.sense_monitor_id

    sense_devices = config_entry.runtime_data.discovered
    device_data = config_entry.runtime_data.device_data
    devices = [
        SenseDevice(device_data, device, sense_monitor_id)
        for device in sense_devices
        if device["tags"]["DeviceListAllowed"] == "true"
    ]

    await _migrate_old_unique_ids(hass, devices)

    async_add_entities(devices)


async def _migrate_old_unique_ids(hass, devices):
    registry = er.async_get(hass)
    for device in devices:
        # Migration of old not so unique ids
        old_entity_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, device.old_unique_id
        )
        if old_entity_id is not None:
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                device.old_unique_id,
                device.unique_id,
            )
            registry.async_update_entity(old_entity_id, new_unique_id=device.unique_id)


def sense_to_mdi(sense_icon):
    """Convert sense icon to mdi icon."""
    return "mdi:{}".format(MDI_ICONS.get(sense_icon, "power-plug"))


class SenseDevice(BinarySensorEntity):
    """Implementation of a Sense energy device binary sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_available = False
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, sense_devices_data, device, sense_monitor_id):
        """Initialize the Sense binary sensor."""
        self._attr_name = device["name"]
        self._id = device["id"]
        self._sense_monitor_id = sense_monitor_id
        self._attr_unique_id = f"{sense_monitor_id}-{self._id}"
        self._attr_icon = sense_to_mdi(device["icon"])
        self._sense_devices_data = sense_devices_data

    @property
    def old_unique_id(self):
        """Return the old not so unique id of the binary sensor."""
        return self._id

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SENSE_DEVICE_UPDATE}-{self._sense_monitor_id}",
                self._async_update_from_data,
            )
        )

    @callback
    def _async_update_from_data(self):
        """Get the latest data, update state. Must not do I/O."""
        new_state = bool(self._sense_devices_data.get_device_by_id(self._id))
        if self._attr_available and self._attr_is_on == new_state:
            return
        self._attr_available = True
        self._attr_is_on = new_state
        self.async_write_ha_state()
