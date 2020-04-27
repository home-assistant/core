"""Support for the Livebox platform."""
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity

from . import COORDINATOR, DOMAIN, LIVEBOX_ID

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker from config entry."""
    datas = hass.data[DOMAIN][config_entry.entry_id]
    box_id = datas[LIVEBOX_ID]
    coordinator = datas[COORDINATOR]

    device_trackers = coordinator.data.get("devices")
    entities = []
    for key, device in device_trackers.items():
        if "IPAddress" and "PhysAddress" in device:
            entity = LiveboxDeviceScannerEntity(key, box_id, coordinator)
            entities.append(entity)
    async_add_entities(entities, update_before_add=True)


class LiveboxDeviceScannerEntity(ScannerEntity):
    """Represent a tracked device."""

    def __init__(self, key, bridge_id, coordinator):
        """Initialize the device tracker."""
        self.box_id = id
        self.coordinator = coordinator
        self.key = key
        self._device = self.coordinator.data.get("devices").get(self.key)
        # self._retry = 0

    @property
    def name(self):
        """Return Entity's default name."""
        return self._device.get("Name")

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.key

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self.coordinator.data.get("devices").get(self.key).get("Active") is True

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_ROUTER

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "via_device": (DOMAIN, self.box_id),
        }

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        _attributs = {
            "ip_address": self.coordinator.data.get("devices")
            .get(self.key)
            .get("IPAddress"),
            "first_seen": self.coordinator.data.get("devices")
            .get(self.key)
            .get("FirstSeen"),
        }
        return _attributs

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self) -> None:
        """Update WLED entity."""
        await self.coordinator.async_request_refresh()

    # ~ @Throttle(SCAN_INTERVAL)
    # ~ async def async_update(self):
    # ~ """Handle polling."""
    # ~ data_status = await self._bridge.async_get_device(self.unique_id)
    # ~ if data_status:
    # ~ self._device = data_status
    # ~ if self._device.get("Active") is False and self._retry < 2:
    # ~ self._retry += 1
    # ~ self._device["Active"] = True
    # ~ elif self._device.get("Active") is False and self._retry == 2:
    # ~ self._device["Active"] = False
    # ~ else:
    # ~ self._retry = 0
    # ~ self._device["Active"] = True
    # ~ _LOGGER.debug(
    # ~ f"Update {self.name} - {self.unique_id} - {self._retry} - {self._device['Active']}"
    # ~ )
