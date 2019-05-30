"""Axis network device abstraction."""

import asyncio
import async_timeout

from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_CAMERA, CONF_EVENTS, CONF_MODEL, DOMAIN, LOGGER

from .errors import AuthenticationRequired, CannotConnect


class AxisNetworkDevice:
    """Manages a Axis device."""

    def __init__(self, hass, config_entry):
        """Initialize the device."""
        self.hass = hass
        self.config_entry = config_entry
        self.available = True

        self.api = None
        self.fw_version = None
        self.product_type = None

        self.listeners = []

    @property
    def host(self):
        """Return the host of this device."""
        return self.config_entry.data[CONF_DEVICE][CONF_HOST]

    @property
    def model(self):
        """Return the model of this device."""
        return self.config_entry.data[CONF_MODEL]

    @property
    def name(self):
        """Return the name of this device."""
        return self.config_entry.data[CONF_NAME]

    @property
    def serial(self):
        """Return the mac of this device."""
        return self.config_entry.data[CONF_MAC]

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = await \
            self.hass.helpers.device_registry.async_get_registry()
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.serial)},
            identifiers={(DOMAIN, self.serial)},
            manufacturer='Axis Communications AB',
            model="{} {}".format(self.model, self.product_type),
            name=self.name,
            sw_version=self.fw_version
        )

    async def async_setup(self):
        """Set up the device."""
        try:
            self.api = await get_device(
                self.hass, self.config_entry.data[CONF_DEVICE])

        except CannotConnect:
            raise ConfigEntryNotReady

        except Exception:  # pylint: disable=broad-except
            LOGGER.error(
                'Unknown error connecting with Axis device on %s', self.host)
            return False

        self.fw_version = self.api.vapix.params.firmware_version
        self.product_type = self.api.vapix.params.prodtype

        if self.config_entry.options[CONF_CAMERA]:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, 'camera'))

        if self.config_entry.options[CONF_EVENTS]:
            task = self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, 'binary_sensor'))

            self.api.stream.connection_status_callback = \
                self.async_connection_status_callback
            self.api.enable_events(event_callback=self.async_event_callback)
            task.add_done_callback(self.start)

        self.config_entry.add_update_listener(self.async_new_address_callback)

        return True

    @property
    def event_new_address(self):
        """Device specific event to signal new device address."""
        return 'axis_new_address_{}'.format(self.serial)

    @staticmethod
    async def async_new_address_callback(hass, entry):
        """Handle signals of device getting new address.

        This is a static method because a class method (bound method),
        can not be used with weak references.
        """
        device = hass.data[DOMAIN][entry.data[CONF_MAC]]
        device.api.config.host = device.host
        async_dispatcher_send(hass, device.event_new_address)

    @property
    def event_reachable(self):
        """Device specific event to signal a change in connection status."""
        return 'axis_reachable_{}'.format(self.serial)

    @callback
    def async_connection_status_callback(self, status):
        """Handle signals of device connection status.

        This is called on every RTSP keep-alive message.
        Only signal state change if state change is true.
        """
        from axis.streammanager import SIGNAL_PLAYING
        if self.available != (status == SIGNAL_PLAYING):
            self.available = not self.available
            async_dispatcher_send(self.hass, self.event_reachable, True)

    @property
    def event_new_sensor(self):
        """Device specific event to signal new sensor available."""
        return 'axis_add_sensor_{}'.format(self.serial)

    @callback
    def async_event_callback(self, action, event_id):
        """Call to configure events when initialized on event stream."""
        if action == 'add':
            async_dispatcher_send(self.hass, self.event_new_sensor, event_id)

    @callback
    def start(self, fut):
        """Start the event stream."""
        self.api.start()

    @callback
    def shutdown(self, event):
        """Stop the event stream."""
        self.api.stop()

    async def async_reset(self):
        """Reset this device to default state."""
        self.api.stop()

        if self.config_entry.options[CONF_CAMERA]:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, 'camera')

        if self.config_entry.options[CONF_EVENTS]:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, 'binary_sensor')

        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()
        self.listeners = []

        return True


async def get_device(hass, config):
    """Create a Axis device."""
    import axis

    device = axis.AxisDevice(
        loop=hass.loop, host=config[CONF_HOST],
        username=config[CONF_USERNAME],
        password=config[CONF_PASSWORD],
        port=config[CONF_PORT], web_proto='http')

    device.vapix.initialize_params(preload_data=False)

    try:
        with async_timeout.timeout(15):
            await hass.async_add_executor_job(
                device.vapix.params.update_brand)
            await hass.async_add_executor_job(
                device.vapix.params.update_properties)
        return device

    except axis.Unauthorized:
        LOGGER.warning("Connected to device at %s but not registered.",
                       config[CONF_HOST])
        raise AuthenticationRequired

    except (asyncio.TimeoutError, axis.RequestError):
        LOGGER.error("Error connecting to the Axis device at %s",
                     config[CONF_HOST])
        raise CannotConnect

    except axis.AxisException:
        LOGGER.exception('Unknown Axis communication error occurred')
        raise AuthenticationRequired
