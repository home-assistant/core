"""Support for the Livebox platform."""
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, DATA_LIVEBOX

_LOGGER = logging.getLogger(__name__)

DATA_LIVEBOX_DISPATCHERS = "livebox_dispatchers"
LIVEBOX_DISCOVERY_NEW = "livebox_discovery_new_{}"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up device tracker from config entry."""

    async def async_discover(device):
        await _async_setup_entities(hass, config_entry, async_add_entities, [device])

    unsub = async_dispatcher_connect(
        hass, LIVEBOX_DISCOVERY_NEW.format(DOMAIN), async_discover
    )
    hass.data[DOMAIN][DATA_LIVEBOX_DISPATCHERS] = []
    hass.data[DOMAIN][DATA_LIVEBOX_DISPATCHERS].append(unsub)

    box_data = hass.data[DOMAIN][DATA_LIVEBOX]
    device_trackers = await box_data.async_devices()
    if device_trackers:
        await _async_setup_entities(
            hass, config_entry, async_add_entities, device_trackers
        )


async def _async_setup_entities(
    hass, config_entry, async_add_entities, device_trackers
):
    """Set up the device trackers."""

    entities = []
    for device in device_trackers:
        if "IPAddress" in device:
            entities.append(
                LiveboxDeviceScannerEntity(
                    config_entry.data["id"], hass.data[DOMAIN][DATA_LIVEBOX], **device
                )
            )

    async_add_entities(entities, update_before_add=True)


class LiveboxDeviceScannerEntity(ScannerEntity):
    """Represent a tracked device."""

    def __init__(self, id, box_data, **kwargs):
        """Initialize the device tracker."""
        self._device = kwargs
        self._box_id = id
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

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""

        for unsub in self._unsubs:
            unsub()
            self._unsubs.remove(unsub)

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
