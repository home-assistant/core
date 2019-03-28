"""Representation of a deCONZ gateway."""
from homeassistant import config_entries
from homeassistant.const import CONF_EVENT, CONF_ID
from homeassistant.core import EventOrigin, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.util import slugify

from .const import (
    _LOGGER, DECONZ_REACHABLE, CONF_ALLOW_CLIP_SENSOR, SUPPORTED_PLATFORMS)


class DeconzGateway:
    """Manages a single deCONZ gateway."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.available = True
        self.api = None
        self._cancel_retry_setup = None

        self.deconz_ids = {}
        self.events = []
        self.listeners = []

    async def async_setup(self, tries=0):
        """Set up a deCONZ gateway."""
        hass = self.hass

        self.api = await get_gateway(
            hass, self.config_entry.data, self.async_add_device_callback,
            self.async_connection_status_callback
        )

        if self.api is False:
            retry_delay = 2 ** (tries + 1)
            _LOGGER.error(
                "Error connecting to deCONZ gateway. Retrying in %d seconds",
                retry_delay)

            async def retry_setup(_now):
                """Retry setup."""
                if await self.async_setup(tries + 1):
                    # This feels hacky, we should find a better way to do this
                    self.config_entry.state = config_entries.ENTRY_STATE_LOADED

            self._cancel_retry_setup = hass.helpers.event.async_call_later(
                retry_delay, retry_setup)

            return False

        for component in SUPPORTED_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(
                    self.config_entry, component))

        self.listeners.append(
            async_dispatcher_connect(
                hass, 'deconz_new_sensor', self.async_add_remote))

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
        async_dispatcher_send(
            self.hass, 'deconz_new_{}'.format(device_type), device)

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
        # If we have a retry scheduled, we were never setup.
        if self._cancel_retry_setup is not None:
            self._cancel_retry_setup()
            self._cancel_retry_setup = None
            return True

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
    from pydeconz import DeconzSession

    session = aiohttp_client.async_get_clientsession(hass)
    deconz = DeconzSession(hass.loop, session, **config,
                           async_add_device=async_add_device_callback,
                           connection_status=async_connection_status_callback)
    result = await deconz.async_load_parameters()

    if result:
        return deconz
    return result


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
