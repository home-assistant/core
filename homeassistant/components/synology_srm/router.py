"""Represent the Synology SRM router and its devices."""
from datetime import timedelta
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)
_LOGGER = logging.getLogger(__name__)


def get_device_from_devices(devices, mac):
    """Get a device based on the MAC address from the list of all devices."""
    return next((device for device in devices if device["mac"] == mac), False)


class SynologySrmRouter:
    """Representation of a Synology SRM router."""

    def __init__(self, hass, client):
        """Initialize a Synology SRM router."""
        self.hass = hass
        self.client = client

        self._unsub_interval = None
        self.devices = []
        self.listeners = []

    async def async_setup(self):
        """Setups the state and trigger a global update."""
        await self._async_update()
        self._unsub_interval = async_track_time_interval(
            self.hass, self._async_update, SCAN_INTERVAL
        )

    async def _async_update(self, now=None):
        """Update the internal state of the router by querying the API."""
        devices = await self.hass.async_add_executor_job(
            self.client.core.get_network_nsm_device
        )

        has_new_devices = False
        for device in devices:
            if not get_device_from_devices(self.devices, device["mac"]):
                has_new_devices = True

        has_deleted_devices = False
        for device in self.devices:
            if not get_device_from_devices(devices, device["mac"]):
                has_deleted_devices = True

        # Save the current state
        self.devices = devices
        _LOGGER.debug("Found %d device(s)", len(devices))

        if has_new_devices:
            async_dispatcher_send(self.hass, self.signal_devices_new)

        if has_deleted_devices:
            async_dispatcher_send(self.hass, self.signal_devices_delete)

        async_dispatcher_send(self.hass, self.signal_devices_update)

    def get_device(self, mac):
        """Get a device connected to the router."""
        return get_device_from_devices(self.devices, mac)

    async def async_unload(self):
        """Stop interacting with the router and prepare for removal from hass."""
        self._unsub_interval()

    @property
    def signal_devices_new(self):
        """Specific Synology SRM event to signal new devices."""
        return f"{DOMAIN}-{self.client.http.host}-devices-new"

    @property
    def signal_devices_update(self):
        """Specific Synology SRM event to signal update on current devices."""
        return f"{DOMAIN}-{self.client.http.host}-devices-update"

    @property
    def signal_devices_delete(self):
        """Specific Synology SRM event to signal deletion of devices."""
        return f"{DOMAIN}-{self.client.http.host}-devices-delete"
