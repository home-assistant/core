"""Support for the Livebox platform."""
import logging

from homeassistant.core import callback
from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, DATA_LIVEBOX, DATA_LIVEBOX_UNSUB

TRACKER_UPDATE = "{}_tracker_update".format(DOMAIN)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker from config entry."""

    @callback
    def _receive_data(device):
        """Receive set location."""
        if device["PhysAddress"] in hass.data[DOMAIN]["devices"]:
            return

        hass.data[DOMAIN]["devices"].add(device["PhysAddress"])

        async_add_entities(
            [
                LiveboxDeviceScannerEntity(
                    config_entry.data["id"], hass.data[DOMAIN][DATA_LIVEBOX], **device
                )
            ]
        )

    hass.data[DOMAIN][DATA_LIVEBOX_UNSUB][
        config_entry.entry_id
    ] = async_dispatcher_connect(hass, TRACKER_UPDATE, _receive_data)

    box_data = hass.data[DOMAIN][DATA_LIVEBOX]
    device_trackers = await box_data.async_devices()
    if not device_trackers:
        return

    entities = []
    for device in device_trackers:
        if "IPAddress" in device:
            hass.data[DOMAIN]["devices"].add(device["PhysAddress"])
            entity = LiveboxDeviceScannerEntity(
                config_entry.data["id"], hass.data[DOMAIN][DATA_LIVEBOX], **device
            )
            entities.append(entity)

    async_add_entities(entities, update_before_add=True)


class LiveboxDeviceScannerEntity(ScannerEntity):
    """Represent a tracked device."""

    def __init__(self, box_id, box_data, **kwargs):
        """Initialize the device tracker."""
        self._device = kwargs
        self._box_id = box_id
        self._box_data = box_data
        self._connected = False
        self._unsubs = []

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
            "manufacturer": "Orange",
            "via_device": (DOMAIN, self._box_id),
        }

    async def async_added_to_hass(self):
        """Register state update callback."""

        await super().async_added_to_hass()
        self._unsubs = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""

        await super().async_will_remove_from_hass()
        self._unsubs()

    async def async_update(self):
        """Handle polling."""

        if await self._update_entity():
            self._connected = True
        else:
            self._connected = False

    async def _update_entity(self):

        device = await self._box_data.async_devices(self._device)
        if device:
            return device[0]["Active"]
        else:
            return False

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""

        return self._connected

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""

        return SOURCE_TYPE_ROUTER

    @callback
    def _async_receive_data(self, device):
        """Mark the device as seen."""

        if device["Name"] != self.name:
            return
        if self._update_entity():
            self.async_write_ha_state()
