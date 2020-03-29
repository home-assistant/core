"""Code to handle a Dynalite bridge."""

from dynalite_devices_lib.dynalite_devices import DynaliteDevices

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_ALL, CONF_HOST, ENTITY_PLATFORMS, LOGGER


class DynaliteBridge:
    """Manages a single Dynalite bridge."""

    def __init__(self, hass, config):
        """Initialize the system based on host parameter."""
        self.hass = hass
        self.area = {}
        self.async_add_devices = {}
        self.waiting_devices = {}
        self.host = config[CONF_HOST]
        # Configure the dynalite devices
        self.dynalite_devices = DynaliteDevices(
            new_device_func=self.add_devices_when_registered,
            update_device_func=self.update_device,
        )
        self.dynalite_devices.configure(config)

    async def async_setup(self):
        """Set up a Dynalite bridge."""
        # Configure the dynalite devices
        LOGGER.debug("Setting up bridge - host %s", self.host)
        return await self.dynalite_devices.async_setup()

    def reload_config(self, config):
        """Reconfigure a bridge when config changes."""
        LOGGER.debug("Reloading bridge - host %s, config %s", self.host, config)
        self.dynalite_devices.configure(config)

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

    @callback
    def register_add_devices(self, platform, async_add_devices):
        """Add an async_add_entities for a category."""
        self.async_add_devices[platform] = async_add_devices
        if platform in self.waiting_devices:
            self.async_add_devices[platform](self.waiting_devices[platform])

    def add_devices_when_registered(self, devices):
        """Add the devices to HA if the add devices callback was registered, otherwise queue until it is."""
        for platform in ENTITY_PLATFORMS:
            platform_devices = [
                device for device in devices if device.category == platform
            ]
            if platform in self.async_add_devices:
                self.async_add_devices[platform](platform_devices)
            else:  # handle it later when it is registered
                if platform not in self.waiting_devices:
                    self.waiting_devices[platform] = []
                self.waiting_devices[platform].extend(platform_devices)
