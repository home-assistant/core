"""
Support for HomematicIP components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematicip_cloud/
"""

import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.core import callback

from .const import (
    DOMAIN, HMIPC_HAPID, HMIPC_AUTHTOKEN, HMIPC_NAME,
    CONF_ACCESSPOINT, CONF_AUTHTOKEN, CONF_NAME)
# Loading the config flow file will register the flow
from .config_flow import configured_haps

REQUIREMENTS = ['homematicip==0.9.6']

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN, default=[]): vol.All(cv.ensure_list, [vol.Schema({
        vol.Optional(CONF_NAME, default=''): vol.Any(cv.string),
        vol.Required(CONF_ACCESSPOINT): cv.string,
        vol.Required(CONF_AUTHTOKEN): cv.string,
    })]),
}, extra=vol.ALLOW_EXTRA)

ATTR_HOME_ID = 'home_id'
ATTR_HOME_NAME = 'home_name'
ATTR_DEVICE_ID = 'device_id'
ATTR_DEVICE_LABEL = 'device_label'
ATTR_STATUS_UPDATE = 'status_update'
ATTR_FIRMWARE_STATE = 'firmware_state'
ATTR_UNREACHABLE = 'unreachable'
ATTR_LOW_BATTERY = 'low_battery'
ATTR_MODEL_TYPE = 'model_type'
ATTR_GROUP_TYPE = 'group_type'
ATTR_DEVICE_RSSI = 'device_rssi'
ATTR_DUTY_CYCLE = 'duty_cycle'
ATTR_CONNECTED = 'connected'
ATTR_SABOTAGE = 'sabotage'
ATTR_OPERATION_LOCK = 'operation_lock'

COMPONENTS = [
    'binary_sensor',
    'light',
    'sensor',
]


async def async_setup(hass, config):
    """Set up the HomematicIP component."""
    hass.data[DOMAIN] = {}

    accesspoints = config.get(DOMAIN, [])

    for conf in accesspoints:
        if conf[CONF_ACCESSPOINT] not in configured_haps(hass):
            hass.async_add_job(hass.config_entries.flow.async_init(
                DOMAIN, source='import', data={
                    HMIPC_HAPID: conf[CONF_ACCESSPOINT],
                    HMIPC_AUTHTOKEN: conf[CONF_AUTHTOKEN],
                    HMIPC_NAME: conf[CONF_NAME],
                }
            ))

    return True


async def async_setup_entry(hass, entry):
    """Set up a bridge from a config entry."""
    hap = HomematicipHAP(hass, entry)

    hapid = entry.data[HMIPC_HAPID].replace('-', '').upper()
    hass.data[DOMAIN][hapid] = hap

    _LOGGER.info('Connected to HomematicIP server, %s.', hapid)
    return await hap.async_init()


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hap = hass.data[DOMAIN].pop(entry.data[HMIPC_HAPID])
    return await hap.async_reset()


class HomematicipHAP(object):
    """Manages HomematicIP http and websocket connection."""

    def __init__(self, hass, config_entry):
        """Initialize HomematicIP cloud connection."""
        from homematicip.aio.home import AsyncHome

        self._hass = hass
        self._ws_close_requested = False
        self._retry_task = None
        self._tries = 0
        self.config_entry = config_entry

        self._hapid = config_entry.data.get(HMIPC_HAPID)

        self.home = AsyncHome(hass.loop, async_get_clientsession(hass))
        self.home.set_auth_token(config_entry.data.get(HMIPC_AUTHTOKEN))

        self.home.on_update(self.async_update)
        self.home.name = config_entry.data.get(HMIPC_NAME)
        self.home.label = 'Access Point'
        self.home.modelType = 'HmIP-HAP'

        self._accesspoint_connected = True

        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_close()
        )

    async def async_init(self):
        """Initialize connection."""
        from homematicip.base.base_connection import HmipConnectionError

        try:
            await self.home.init(self._hapid)
            await self.home.get_current_state()
            self._hass.loop.create_task(self.async_connect())
        except HmipConnectionError:
            _LOGGER.error('Failed to connect to the sever, %s.', self._hapid)
            return False

        for component in COMPONENTS:
            self._hass.async_add_job(
                self._hass.config_entries.async_forward_entry_setup(
                    self.config_entry, component)
            )

        return True

    @callback
    def async_update(self, *args, **kwargs):
        """Async update the home device.

        Triggered when the hmip HOME_CHANGED event has fired.
        There are several occasions for this event to happen.
        We are only interested to check whether the access point
        is still connected. If not, device state changes cannot
        be forwarded to hass. So if access point is disconnected all devices
        are set to unavailable.
        """
        if not self.home.connected:
            _LOGGER.error(
                "HMIP access point has lost connection with the cloud")
            self._accesspoint_connected = False
            self.set_all_to_unavailable()
        elif not self._accesspoint_connected:
            # Explicitly getting an update as device states might have
            # changed during access point disconnect."""

            job = self._hass.async_add_job(self.get_state())
            job.add_done_callback(self.get_state_finished)

    async def get_state(self):
        """Update hmip state and tell hass."""
        await self.home.get_current_state()
        self.update_all()

    def get_state_finished(self, future):
        """Execute when get_state coroutine has finished."""
        from homematicip.base.base_connection import HmipConnectionError

        try:
            future.result()
        except HmipConnectionError:
            # Somehow connection could not recover. Will disconnect and
            # so reconnect loop is taking over.
            _LOGGER.error(
                "updating state after himp access point reconnect failed.")
            self._hass.async_add_job(self.home.disable_events())

    def set_all_to_unavailable(self):
        """Set all devices to unavailable and tell Hass."""
        for device in self.home.devices:
            device.unreach = True
        self.update_all()

    def update_all(self):
        """Signal all devices to update their state."""
        for device in self.home.devices:
            device.fire_update_event()

    async def _handle_connection(self):
        """Handle websocket connection."""
        from homematicip.base.base_connection import HmipConnectionError

        await self.home.get_current_state()
        hmip_events = await self.home.enable_events()
        try:
            await hmip_events
        except HmipConnectionError:
            return

    async def async_connect(self):
        """Start websocket connection."""
        self._tries = 0
        while True:
            await self._handle_connection()
            if self._ws_close_requested:
                break
            self._ws_close_requested = False
            self._tries += 1
            try:
                self._retry_task = self._hass.async_add_job(asyncio.sleep(
                    2 ** min(9, self._tries), loop=self._hass.loop))
                await self._retry_task
            except asyncio.CancelledError:
                break
            _LOGGER.info('Reconnect (%s) to the HomematicIP cloud server.',
                         self._tries)

    async def async_close(self):
        """Close the websocket connection."""
        self._ws_close_requested = True
        if self._retry_task is not None:
            self._retry_task.cancel()
        await self.home.disable_events()
        _LOGGER.info("Closed connection to HomematicIP cloud server.")


class HomematicipGenericDevice(Entity):
    """Representation of an HomematicIP generic device."""

    def __init__(self, home, device, post=None):
        """Initialize the generic device."""
        self._home = home
        self._device = device
        self.post = post
        _LOGGER.info('Setting up %s (%s)', self.name,
                     self._device.modelType)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._device.on_update(self._device_changed)

    def _device_changed(self, json, **kwargs):
        """Handle device state changes."""
        _LOGGER.debug('Event %s (%s)', self.name, self._device.modelType)
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the generic device."""
        name = self._device.label
        if (self._home.name is not None and self._home.name != ''):
            name = "{} {}".format(self._home.name, name)
        if (self.post is not None and self.post != ''):
            name = "{} {}".format(name, self.post)
        return name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Device available."""
        return not self._device.unreach

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        return {
            ATTR_LOW_BATTERY: self._device.lowBat,
            ATTR_MODEL_TYPE: self._device.modelType
        }
