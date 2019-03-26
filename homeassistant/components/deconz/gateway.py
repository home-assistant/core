"""Representation of a deCONZ gateway."""
import asyncio
import async_timeout

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import CONF_EVENT, CONF_HOST, CONF_ID
from homeassistant.core import EventOrigin, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.util import slugify

from .const import (
    _LOGGER, DECONZ_REACHABLE, CONF_ALLOW_CLIP_SENSOR, NEW_DEVICE, NEW_SENSOR,
    SUPPORTED_PLATFORMS)
from .errors import AuthenticationRequired, CannotConnect


class DeconzGateway:
    """Manages a single deCONZ gateway."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.available = True
        self.api = None

        self.deconz_ids = {}
        self.events = []
        self.listeners = []

    async def async_setup(self):
        """Set up a deCONZ gateway."""
        hass = self.hass

        try:
            self.api = await get_gateway(
                hass, self.config_entry.data, self.async_add_device_callback,
                self.async_connection_status_callback
            )

        except CannotConnect:
            raise ConfigEntryNotReady

        except Exception:  # pylint: disable=broad-except
            _LOGGER.error('Error connecting with deCONZ gateway')
            return False

        for component in SUPPORTED_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    self.config_entry, component))

        self.listeners.append(
            async_dispatcher_connect(
                hass, NEW_SENSOR, self.async_add_remote))

        self.async_add_remote(self.api.sensors.values())

        self.api.start()

        return True

    @callback
    def async_connection_status_callback(self, available):
        """Handle signals of gateway connection status."""
        self.available = available
        async_dispatcher_send(
            self.hass, DECONZ_REACHABLE, {'state': True, 'attr': 'reachable'})

    @callback
    def async_add_device_callback(self, device_type, device):
        """Handle event of new device creation in deCONZ."""
        if not isinstance(device, list):
            device = [device]
        async_dispatcher_send(self.hass, NEW_DEVICE[device_type], device)

    @callback
    def async_add_remote(self, sensors):
        """Set up remote from deCONZ."""
        from pydeconz.sensor import SWITCH as DECONZ_REMOTE
        allow_clip_sensor = self.config_entry.data.get(
            CONF_ALLOW_CLIP_SENSOR, True)
        for sensor in sensors:
            if sensor.type in DECONZ_REMOTE and \
               not (not allow_clip_sensor and sensor.type.startswith('CLIP')):
                self.events.append(DeconzEvent(self.hass, sensor))

    @callback
    def shutdown(self, event):
        """Wrap the call to deconz.close.

        Used as an argument to EventBus.async_listen_once.
        """
        self.api.close()

    async def async_reset(self):
        """Reset this gateway to default state.

        Will cancel any scheduled setup retry and will unload
        the config entry.
        """
        self.api.close()

        for component in SUPPORTED_PLATFORMS:
            await self.hass.config_entries.async_forward_entry_unload(
                self.config_entry, component)

        for unsub_dispatcher in self.listeners:
            unsub_dispatcher()
        self.listeners = []

        for event in self.events:
            event.async_will_remove_from_hass()
            self.events.remove(event)

        self.deconz_ids = {}
        return True


async def get_gateway(hass, config, async_add_device_callback,
                      async_connection_status_callback):
    """Create a gateway object and verify configuration."""
    from pydeconz import DeconzSession, errors

    session = aiohttp_client.async_get_clientsession(hass)

    deconz = DeconzSession(hass.loop, session, **config,
                           async_add_device=async_add_device_callback,
                           connection_status=async_connection_status_callback)
    try:
        with async_timeout.timeout(10):
            await deconz.async_load_parameters()
        return deconz

    except errors.Unauthorized:
        _LOGGER.warning("Invalid key for deCONZ at %s", config[CONF_HOST])
        raise AuthenticationRequired

    except (asyncio.TimeoutError, errors.RequestError):
        _LOGGER.error(
            "Error connecting to deCONZ gateway at %s", config[CONF_HOST])
        raise CannotConnect


class DeconzEvent:
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, hass, device):
        """Register callback that will be used for signals."""
        self._hass = hass
        self._device = device
        self._device.register_async_callback(self.async_update_callback)
        self._event = 'deconz_{}'.format(CONF_EVENT)
        self._id = slugify(self._device.name)
        _LOGGER.debug("deCONZ event created: %s", self._id)

    @callback
    def async_will_remove_from_hass(self) -> None:
        """Disconnect event object when removed."""
        self._device.remove_callback(self.async_update_callback)
        self._device = None

    @callback
    def async_update_callback(self, reason):
        """Fire the event if reason is that state is updated."""
        if reason['state']:
            data = {CONF_ID: self._id, CONF_EVENT: self._device.state}
            self._hass.bus.async_fire(self._event, data, EventOrigin.remote)
