"""Support for the Livebox platform."""
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_LIVEBOX, DOMAIN, ID_BOX

TRACKER_UPDATE = "{}_tracker_update".format(DOMAIN)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker from config entry."""

    bridge_id = hass.data[DOMAIN][ID_BOX]
    bridge = hass.data[DOMAIN][DATA_LIVEBOX]

    device_trackers = await bridge.async_get_devices()
    entities = []
    for device in device_trackers:
        if "IPAddress" in device:
            entity = LiveboxDeviceScannerEntity(bridge_id, device, bridge)
            entities.append(entity)
    async_add_entities(entities, update_before_add=True)


class LiveboxDeviceScannerEntity(ScannerEntity):
    """Represent a tracked device."""

    def __init__(self, bridge_id, device, session):
        """Initialize the device tracker."""
        self._bridge_id = id
        self._device = device
        self._unsubs = []
        self._session = session

    @property
    def name(self):
        """Return Entity's default name."""
        return self._device["Name"]

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device["PhysAddress"]

    @property
    def device_info(self):
        """Return the device info."""

        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "via_device": (DOMAIN, self._bridge_id),
        }

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        _attributs = {
            "ip_address": self._device.get("IPAddress"),
            "first_seen": self._device.get("FirstSeen"),
        }
        return _attributs

    async def async_added_to_hass(self):
        """Register state update callback."""
        await super().async_added_to_hass()
        self._unsubs = async_dispatcher_connect(
            self.hass,
            TRACKER_UPDATE,
            self._async_receive_data(self._bridge_id, self._device, self._session),
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        await super().async_will_remove_from_hass()
        self._unsubs()

    async def async_update(self):
        """Handle polling."""
        _LOGGER.debug(f"Update {self.name} - {self.unique_id} - {self.is_connected}")
        self._device = await self._session.async_get_device(self.unique_id)

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self._device["Active"] is True

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_ROUTER

    @callback
    async def _async_receive_data(self, bridge_id, device, session):
        if await self.async_update():
            self.async_write_ha_state()
