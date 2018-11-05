"""Axis network device abstraction."""

import asyncio
import async_timeout

from homeassistant import config_entries
from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_USERNAME)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_CAMERA, CONF_DEVICE, CONF_EVENTS, CONF_MODEL_ID, LOGGER
from .errors import AuthenticationRequired, CannotConnect


class AxisNetworkDevice:
    """Manages a Axis device."""

    def __init__(self, hass, config_entry):
        """"""
        self.hass = hass
        self.config_entry = config_entry
        self.available = True
        self.api = None
        self.fw_version = None
        self.product_type = None
        self._cancel_retry_setup = None

        self.listeners = []

    @property
    def host(self):
        """Return the host of this device."""
        return self.config_entry.data[CONF_DEVICE][CONF_HOST]

    @property
    def model_id(self):
        """Return the model of this device."""
        return self.config_entry.data[CONF_MODEL_ID]

    @property
    def name(self):
        """Return the name of this device."""
        return self.config_entry.data[CONF_NAME]

    @property
    def serial(self):
        """Return the mac of this device."""
        return self.config_entry.data[CONF_MAC]

    async def async_setup(self, tries=0):
        """Set up the device."""
        from axis.vapix import VAPIX_FW_VERSION, VAPIX_PROD_TYPE

        hass = self.hass

        try:
            self.api, _ = await get_device(
                hass, self.config_entry.data[CONF_DEVICE],
                event_types=self.config_entry.data[CONF_EVENTS],
                signal_callback=self.async_signal_callback)

            self.fw_version = await hass.async_add_executor_job(
                self.api.vapix.get, VAPIX_FW_VERSION)

            self.product_type = await hass.async_add_executor_job(
                self.api.vapix.get, VAPIX_PROD_TYPE)

        except CannotConnect:
            retry_delay = 2 ** (tries + 1)
            LOGGER.error("Error connecting to the Axis device on %s. Retrying "
                         "in %d seconds", self.host, retry_delay)

            async def retry_setup(_now):
                """Retry setup."""
                if await self.async_setup(tries + 1):
                    # This feels hacky, we should find a better way to do this
                    self.config_entry.state = config_entries.ENTRY_STATE_LOADED

            self._cancel_retry_setup = hass.helpers.event.async_call_later(
                retry_delay, retry_setup)

            return False

        except Exception:  # pylint: disable=broad-except
            LOGGER.error(
                'Unknown error connecting with Axis device on %s.', self.host)
            return False

        if self.config_entry.data[CONF_CAMERA]:
            self.hass.async_create_task(
                self.hass.config_entries.async_forward_entry_setup(
                    self.config_entry, 'camera'))

        if self.config_entry.data[CONF_EVENTS]:
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

    async def async_reset(self):
        """Reset this device to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        # If we have a retry scheduled, we were never setup.
        if self._cancel_retry_setup is not None:
            self._cancel_retry_setup()
            self._cancel_retry_setup = None
            return True

        if self.config_entry.data[CONF_CAMERA]:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, 'camera')

        if self.config_entry.data[CONF_EVENTS]:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, 'binary_sensor')
            self.api.stop()

        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()
        self.listeners = []

        return True


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
        with async_timeout.timeout(5):
            serial_number = await hass.async_add_executor_job(
                device.vapix.get, axis.vapix.VAPIX_SERIAL_NUMBER)

        return device, serial_number

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
