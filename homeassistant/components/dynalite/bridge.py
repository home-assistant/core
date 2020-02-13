"""Code to handle a Dynalite bridge."""

from dynalite_devices_lib import DynaliteDevices
from dynalite_lib import CONF_ALL

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DATA_CONFIGS, DOMAIN, LOGGER


class DynaliteBridge:
    """Manages a single Dynalite bridge."""

    def __init__(self, hass, config_entry):
        """Initialize the system based on host parameter."""
        self.config_entry = config_entry
        self.hass = hass
        self.area = {}
        self.async_add_devices = None
        self.waiting_devices = []
        self.config = None
        self.host = config_entry.data[CONF_HOST]
        self.config = hass.data[DOMAIN][DATA_CONFIGS][self.host]
        # Configure the dynalite devices
        self.dynalite_devices = DynaliteDevices(
            config=self.config,
            newDeviceFunc=self.add_devices_when_registered,
            updateDeviceFunc=self.update_device,
        )

    async def async_setup(self, tries=0):
        """Set up a Dynalite bridge."""
        # Configure the dynalite devices
        await self.dynalite_devices.async_setup()

        self.hass.async_create_task(
            self.hass.config_entries.async_forward_entry_setup(
                self.config_entry, "light"
            )
        )

        return True

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
    def register_add_devices(self, async_add_devices):
        """Add an async_add_entities for a category."""
        self.async_add_devices = async_add_devices
        if self.waiting_devices:
            self.async_add_devices(self.waiting_devices)

    def add_devices_when_registered(self, devices):
        """Add the devices to HA if async_add_entities was registered, otherwise queue until it is."""
        if not devices:
            return
        if self.async_add_devices:
            self.async_add_devices(devices)
        else:  # handle it later when it is registered
            self.waiting_devices.extend(devices)

    async def async_reset(self):
        """Reset this bridge to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        result = await self.hass.config_entries.async_forward_entry_unload(
            self.config_entry, "light"
        )
        # None and True are OK
        return result
