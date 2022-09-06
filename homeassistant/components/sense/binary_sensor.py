"""Support for monitoring a Sense energy sensor device."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTRIBUTION,
    DOMAIN,
    MDI_ICONS,
    SENSE_DATA,
    SENSE_DEVICE_UPDATE,
    SENSE_DEVICES_DATA,
    SENSE_DISCOVERED_DEVICES_DATA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sense binary sensor."""
    data = hass.data[DOMAIN][config_entry.entry_id][SENSE_DATA]
    sense_devices_data = hass.data[DOMAIN][config_entry.entry_id][SENSE_DEVICES_DATA]
    sense_monitor_id = data.sense_monitor_id

    sense_devices = hass.data[DOMAIN][config_entry.entry_id][
        SENSE_DISCOVERED_DEVICES_DATA
    ]
    devices = [
        SenseDevice(sense_devices_data, device, sense_monitor_id)
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

    _attr_should_poll = False

    def __init__(self, sense_devices_data, device, sense_monitor_id):
        """Initialize the Sense binary sensor."""
        self._name = device["name"]
        self._id = device["id"]
        self._sense_monitor_id = sense_monitor_id
        self._unique_id = f"{sense_monitor_id}-{self._id}"
        self._icon = sense_to_mdi(device["icon"])
        self._sense_devices_data = sense_devices_data
        self._state = None
        self._available = False

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def available(self):
        """Return the availability of the binary sensor."""
        return self._available

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the binary sensor."""
        return self._unique_id

    @property
    def old_unique_id(self):
        """Return the old not so unique id of the binary sensor."""
        return self._id

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def icon(self):
        """Return the icon of the binary sensor."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the binary sensor."""
        return BinarySensorDeviceClass.POWER

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
        if self._available and self._state == new_state:
            return
        self._available = True
        self._state = new_state
        self.async_write_ha_state()
