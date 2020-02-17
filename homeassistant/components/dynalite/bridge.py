"""Code to handle a Dynalite bridge."""

import asyncio

from dynalite_devices_lib import DynaliteDevices

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_ALL, CONF_HOST, LOGGER

CONNECT_TIMEOUT = 30
CONNECT_INTERVAL = 1


class DynaliteBridge:
    """Manages a single Dynalite bridge."""

    def __init__(self, hass, config):
        """Initialize the system based on host parameter."""
        self.hass = hass
        self.area = {}
        self.async_add_devices = None
        self.waiting_devices = []
        self.host = config[CONF_HOST]
        # Configure the dynalite devices
        self.dynalite_devices = DynaliteDevices(
            config=config,
            newDeviceFunc=self.add_devices_when_registered,
            updateDeviceFunc=self.update_device,
        )

    async def async_setup(self):
        """Set up a Dynalite bridge."""
        # Configure the dynalite devices
        return await self.dynalite_devices.async_setup()

    def update_signal(self, device=None):
        """Create signal to use to trigger entity update."""
        if device:
            signal = f"dynalite-update-{self.host}-{device.unique_id}"
        else:
            signal = f"dynalite-update-{self.host}"
        return signal

    @callback
    def update_device(self, device):
        """Call when a device or all devices should be updated."""
        if device == CONF_ALL:
            # This is used to signal connection or disconnection, so all devices may become available or not.
            log_string = (
                "Connected" if self.dynalite_devices.available else "Disconnected"
            )
            LOGGER.info("%s to dynalite host", log_string)
            async_dispatcher_send(self.hass, self.update_signal())
        else:
            async_dispatcher_send(self.hass, self.update_signal(device))

    async def try_connection(self):
        """Try to connect to dynalite with timeout."""
        # Currently by polling. Future - will need to change the library to be proactive
        for _ in range(0, CONNECT_TIMEOUT):
            if self.dynalite_devices.available:
                return True
            await asyncio.sleep(CONNECT_INTERVAL)
        return False

    @callback
    def register_add_devices(self, async_add_devices):
        """Add an async_add_entities for a category."""
        self.async_add_devices = async_add_devices
        if self.waiting_devices:
            self.async_add_devices(self.waiting_devices)

    def add_devices_when_registered(self, devices):
        """Add the devices to HA if the add devices callback was registered, otherwise queue until it is."""
        if not devices:
            return
        if self.async_add_devices:
            self.async_add_devices(devices)
        else:  # handle it later when it is registered
            self.waiting_devices.extend(devices)
