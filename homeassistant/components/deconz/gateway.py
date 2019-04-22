"""Representation of a deCONZ gateway."""
import asyncio
import async_timeout

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import CONF_EVENT, CONF_HOST, CONF_ID
from homeassistant.core import EventOrigin, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.util import slugify

from .const import (
    _LOGGER, CONF_ALLOW_CLIP_SENSOR, CONF_ALLOW_DECONZ_GROUPS, CONF_BRIDGEID,
    CONF_MASTER_GATEWAY, DOMAIN, NEW_DEVICE, NEW_SENSOR, SUPPORTED_PLATFORMS)
from .errors import AuthenticationRequired, CannotConnect


@callback
def get_gateway_from_config_entry(hass, config_entry):
    """Return gateway with a matching bridge id."""
    return hass.data[DOMAIN][config_entry.data[CONF_BRIDGEID]]


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

    @property
    def bridgeid(self) -> str:
        """Return the unique identifier of the gateway."""
        return self.config_entry.data[CONF_BRIDGEID]

    @property
    def master(self) -> bool:
        """Gateway which is used with deCONZ services without defining id."""
        return self.config_entry.options[CONF_MASTER_GATEWAY]

    @property
    def allow_clip_sensor(self) -> bool:
        """Allow loading clip sensor from gateway."""
        return self.config_entry.data.get(CONF_ALLOW_CLIP_SENSOR, True)

    @property
    def allow_deconz_groups(self) -> bool:
        """Allow loading deCONZ groups from gateway."""
        return self.config_entry.data.get(CONF_ALLOW_DECONZ_GROUPS, True)

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = await \
            self.hass.helpers.device_registry.async_get_registry()
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(CONNECTION_NETWORK_MAC, self.api.config.mac)},
            identifiers={(DOMAIN, self.api.config.bridgeid)},
            manufacturer='Dresden Elektronik',
            model=self.api.config.modelid,
            name=self.api.config.name,
            sw_version=self.api.config.swversion
        )

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

        self.listeners.append(async_dispatcher_connect(
            hass, self.async_event_new_device(NEW_SENSOR),
            self.async_add_remote))

        self.async_add_remote(self.api.sensors.values())

        self.api.start()

        self.config_entry.add_update_listener(self.async_new_address_callback)

        return True

    @staticmethod
    async def async_new_address_callback(hass, entry):
        """Handle signals of gateway getting new address.

        This is a static method because a class method (bound method),
        can not be used with weak references.
        """
        gateway = hass.data[DOMAIN][entry.data[CONF_BRIDGEID]]
        gateway.api.close()
        gateway.api.host = entry.data[CONF_HOST]
        gateway.api.start()

    @property
    def event_reachable(self):
        """Gateway specific event to signal a change in connection status."""
        return 'deconz_reachable_{}'.format(self.bridgeid)

    @callback
    def async_connection_status_callback(self, available):
        """Handle signals of gateway connection status."""
        self.available = available
        async_dispatcher_send(self.hass, self.event_reachable,
                              {'state': True, 'attr': 'reachable'})

    @callback
    def async_event_new_device(self, device_type):
        """Gateway specific event to signal new device."""
        return NEW_DEVICE[device_type].format(self.bridgeid)

    @callback
    def async_add_device_callback(self, device_type, device):
        """Handle event of new device creation in deCONZ."""
        if not isinstance(device, list):
            device = [device]
        async_dispatcher_send(
            self.hass, self.async_event_new_device(device_type), device)

    @callback
    def async_add_remote(self, sensors):
        """Set up remote from deCONZ."""
        from pydeconz.sensor import SWITCH as DECONZ_REMOTE
        for sensor in sensors:
            if sensor.type in DECONZ_REMOTE and \
               not (not self.allow_clip_sensor and
                    sensor.type.startswith('CLIP')):
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
