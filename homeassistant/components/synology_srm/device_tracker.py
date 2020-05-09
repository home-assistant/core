"""Device tracker for Synology SRM routers."""
import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_ROUTER
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DEVICE_ATTRIBUTE_ALIAS, DEVICE_ICON, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up device tracker for the Synology SRM component."""
    router = hass.data[DOMAIN][entry.unique_id]
    devices = set()

    @callback
    def async_add_new_devices():
        """Add new devices from the router to Hass."""
        async_add_new_entities(router, async_add_entities, devices)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_devices_new, async_add_new_devices)
    )

    # Add initial devices
    async_add_new_devices()


@callback
def async_add_new_entities(router, async_add_entities, devices):
    """Add only new devices entities from the router."""
    new_devices = []

    for device in router.devices:
        if device["mac"] in devices:
            continue

        new_devices.append(SynologySrmEntity(router, device))
        devices.add(device["mac"])

    if new_devices:
        async_add_entities(new_devices, True)


class SynologySrmEntity(ScannerEntity):
    """Representation of a device connected to the Synology SRM router."""

    def __init__(self, router, device):
        """Initialize a Synology SRM device."""
        self.router = router
        self.device = device

        self.mac = device["mac"]

        self.update_dispatcher = None
        self.delete_dispatcher = None

    def _get(self, parameter=None, default=None):
        """Get internal parameter stored in the router."""
        if not parameter:
            return self.device

        if not self.device or parameter not in self.device:
            return default

        return self.device[parameter]

    @property
    def unique_id(self):
        """Return a unique identifier (the MAC address)."""
        return self._get("mac")

    @property
    def name(self):
        """Return the name of the entity."""
        return self._get("hostname")

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self._get("is_online")

    @property
    def source_type(self):
        """Return the source type of the entity."""
        return SOURCE_TYPE_ROUTER

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        filtered_attributes = {}
        device = self._get()

        for attribute, alias in DEVICE_ATTRIBUTE_ALIAS.items():
            value = device.get(attribute)
            if value is None:
                continue
            attr = alias or attribute
            filtered_attributes[attr] = value

        return filtered_attributes

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        # 1 - Synology device types
        device_type = self._get("dev_type")
        if device_type in DEVICE_ICON:
            return DEVICE_ICON[device_type]

        # 2 - Wi-Fi signal strength
        if self._get("connection") == "wifi":
            strength = self._get("signalstrength", 100)
            thresholds = [70, 50, 30, 0]
            for idx, threshold in enumerate(thresholds):
                if strength >= threshold:
                    return "mdi:wifi-strength-{}".format(len(thresholds) - idx)

        # Fallback to a classical icon
        return "mdi:ethernet"

    @property
    def should_poll(self):
        """No need to poll. Updates are managed by the router."""
        return False

    async def async_update(self):
        """Update the current device."""
        device = self.router.get_device(self.mac)
        if device:
            self.device = device

    async def async_added_to_hass(self):
        """Register state update/delete callback."""
        self.update_dispatcher = async_dispatcher_connect(
            self.hass, self.router.signal_devices_update, self._async_update_callback
        )

        self.delete_dispatcher = async_dispatcher_connect(
            self.hass, self.router.signal_devices_delete, self._async_delete_callback
        )

    async def _async_update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def _async_delete_callback(self):
        """Remove this entity."""
        if not self.router.get_device(self.mac):
            # Remove this entity if parameters are not
            # present in the router anymore
            self.hass.async_create_task(self.async_remove())

    async def async_will_remove_from_hass(self):
        """Call when entity will be removed from hass."""
        self.update_dispatcher()
        self.delete_dispatcher()
