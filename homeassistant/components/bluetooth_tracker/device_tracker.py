"""Tracking for bluetooth devices."""
import asyncio
import logging
from typing import Any, Callable, List, Optional, Set, Tuple

# pylint: disable=import-error
import bluetooth
from bt_proximity import BluetoothRSSI
import voluptuous as vol

from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    SCAN_INTERVAL,
    SOURCE_TYPE_BLUETOOTH,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import device_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BT_PREFIX = "BT_"

TRACKER_UPDATE = "bluetooth_tracker_update"

CONF_REQUEST_RSSI = "request_rssi"
CONF_DEVICE_ID = "device_id"
CONF_DISCOVER_NEW_DEVICES = "discover_new_devices"

DEFAULT_DEVICE_ID = -1
DEFAULT_DISCOVER_NEW_DEVICES = True
DEFAULT_REQUEST_RSSI = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_DISCOVER_NEW_DEVICES, default=DEFAULT_DISCOVER_NEW_DEVICES
        ): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_REQUEST_RSSI, default=DEFAULT_REQUEST_RSSI): cv.boolean,
        vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): vol.All(
            vol.Coerce(int), vol.Range(min=-1)
        ),
    }
)


def discover_devices(device_id: int) -> List[Tuple[str, str]]:
    """Discover Bluetooth devices."""
    result = bluetooth.discover_devices(
        duration=8,
        lookup_names=True,
        flush_cache=True,
        lookup_class=False,
        device_id=device_id,
    )
    _LOGGER.debug("Bluetooth devices discovered = %d", len(result))
    return result


def lookup_name(mac: str) -> Optional[str]:
    """Lookup a Bluetooth device name."""
    _LOGGER.debug("Scanning %s", mac)
    return bluetooth.lookup_name(mac, timeout=5)


async def load_initial_entities(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[List[Any]],
) -> Set[str]:
    """Load tracked entities from device registry."""
    device_registry_instance = await device_registry.async_get_registry(hass)
    macs: Set[str] = {
        mac
        for device in device_registry_instance.devices.values()
        for domain, mac in device.identifiers
        if domain == DOMAIN
    }

    entities = []
    for mac in macs:
        hass.data[DOMAIN]["devices"].add(mac)
        entity = BluetoothEntity(config_entry, mac, None, {})
        entities.append(entity)

    async_add_entities(entities)

    return macs


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[List[Any]],
):
    """Set up a bluetooth device tracker."""
    device_id: int = config_entry.data[CONF_DEVICE_ID]
    interval = config_entry.options[CONF_SCAN_INTERVAL]
    request_rssi: bool = config_entry.options[CONF_REQUEST_RSSI]
    discover_new_devices: bool = config_entry.options[CONF_TRACK_NEW]

    _LOGGER.debug("Tracking new devices is set to %s", discover_new_devices)

    update_bluetooth_lock = asyncio.Lock()
    macs = load_initial_entities(hass, config_entry, async_add_entities)

    if request_rssi:
        _LOGGER.debug("Detecting RSSI for devices")

    def see_device(mac: str, device_name: str, rssi=None) -> None:
        """Mark a device as seen."""
        attributes = {}
        if rssi is not None:
            attributes["rssi"] = rssi

        if mac in macs:
            async_dispatcher_send(hass, TRACKER_UPDATE, mac, device_name, attributes)
            return

        entity = BluetoothEntity(config_entry, mac, device_name, attributes)
        macs.add(mac)
        async_add_entities([entity])

    async def retrieve_bluetooth_rssi(mac: str) -> Optional[int]:
        if not request_rssi:
            return None

        client = BluetoothRSSI(mac)
        rssi = await hass.async_add_executor_job(client.request_rssi)
        client.close()

        return rssi

    async def perform_bluetooth_update():
        """Discover Bluetooth devices and update status."""
        _LOGGER.debug("Performing Bluetooth devices discovery and update")

        try:
            if discover_new_devices:
                devices = await hass.async_add_executor_job(discover_devices, device_id)
                for mac, device_name in devices:
                    # macs is already a set, won't be added twice
                    macs.add(mac)

            for mac in macs:
                device_name = await hass.async_add_executor_job(lookup_name, mac)
                if device_name is None:
                    # Could not lookup device name, device probably away
                    continue

                rssi = await retrieve_bluetooth_rssi(mac)
                see_device(mac, device_name, rssi)

        except bluetooth.BluetoothError:
            _LOGGER.exception("Error looking up Bluetooth device")

    async def update_bluetooth(now=None):
        """Lookup Bluetooth devices and update status."""

        # If an update is in progress, we don't do anything
        if update_bluetooth_lock.locked():
            _LOGGER.debug(
                "Previous execution of update_bluetooth "
                "is taking longer than the scheduled update of interval %s",
                interval,
            )
            return

        async with update_bluetooth_lock:
            await perform_bluetooth_update()

    hass.async_create_task(update_bluetooth())
    async_track_time_interval(hass, update_bluetooth, interval)


class BluetoothEntity(ScannerEntity):
    """Represent a tracked device that is on a scanned bluetooth network."""

    def __init__(
        self, config_entry: ConfigEntry, mac: str, device_name: str, attributes: dict
    ):
        """Set up bluetooth entity."""
        self.mac = mac
        self._attributes = attributes
        self._config_entry = config_entry
        self._last_seen = dt_util.utcnow()
        self._name = device_name
        self._unsub_dispatcher: Optional[Callable] = None

    @property
    def device_info(self):
        """Return the device info."""
        return {"name": self.name, "identifiers": {(DOMAIN, self.mac)}}

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        return self._attributes

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        if (
            dt_util.utcnow() - self._last_seen
            < self._config_entry.options[CONF_CONSIDER_HOME]
        ):
            return True

        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self.mac

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_BLUETOOTH

    async def async_added_to_hass(self):
        """Register state update callback."""
        _LOGGER.debug("New Bluetooth Device %s (%s)", self.name, self.mac)
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()

    @callback
    def _async_receive_data(self, mac: str, device_name: str, attributes: dict):
        """Mark the device as seen."""
        if mac != self.mac:
            return

        self._last_seen = dt_util.utcnow()
        self._attributes.update(attributes)
        self._name = device_name
        self.async_write_ha_state()
