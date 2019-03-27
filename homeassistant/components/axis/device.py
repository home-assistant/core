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
        from axis.vapix import VAPIX_FW_VERSION, VAPIX_PROD_TYPE

        hass = self.hass

        try:
            self.api = await get_device(
                hass, self.config_entry.data[CONF_DEVICE],
                event_types='on', signal_callback=self.async_signal_callback)

        except CannotConnect:
            raise ConfigEntryNotReady

        except Exception:  # pylint: disable=broad-except
            LOGGER.error(
                'Unknown error connecting with Axis device on %s', self.host)
            return False

        self.fw_version = self.api.vapix.get_param(VAPIX_FW_VERSION)
        self.product_type = self.api.vapix.get_param(VAPIX_PROD_TYPE)

        if self.config_entry.options[CONF_CAMERA]:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, 'camera'))

        if self.config_entry.options[CONF_EVENTS]:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, 'binary_sensor'))
            self.api.start()

        return True

    @callback
    def async_signal_callback(self, action, event):
        """Call to configure events when initialized on event stream."""
        if action == 'add':
            async_dispatcher_send(self.hass, 'axis_add_sensor', event)

    @callback
    def shutdown(self, event):
        """Stop the event stream."""
        self.api.stop()


async def get_device(hass, config, event_types=None, signal_callback=None):
    """Create a Axis device."""
    import axis

    device = axis.AxisDevice(
        loop=hass.loop, host=config[CONF_HOST],
        username=config[CONF_USERNAME],
        password=config[CONF_PASSWORD],
        port=config[CONF_PORT], web_proto='http',
        event_types=event_types, signal=signal_callback)

    try:
        with async_timeout.timeout(15):
            await hass.async_add_executor_job(device.vapix.load_params)
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
