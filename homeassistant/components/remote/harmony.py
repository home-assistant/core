"""
Support for Harmony Hub devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remote.harmony/
"""
import asyncio
import json
import logging
from datetime import timedelta
from pathlib import Path

import voluptuous as vol

from homeassistant.components import remote
from homeassistant.components.remote import (
    ATTR_ACTIVITY, ATTR_DELAY_SECS, ATTR_DEVICE, ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS, DOMAIN, PLATFORM_SCHEMA)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT, EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import slugify

# REQUIREMENTS = ['pyharmony==1.0.22']
REQUIREMENTS = [
    'https://github.com/home-assistant/pyharmony/archive/'
    '31efd339a3c39e7b8f58e823a0eddb59013e03ae.zip'
    '#pyharmony==1.0.21b1'
]

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8088
SCAN_INTERVAL = timedelta(seconds=5)
DEVICES = []
CONF_DEVICE_CACHE = 'harmony_device_cache'

SERVICE_SYNC = 'harmony_sync'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(ATTR_ACTIVITY): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(ATTR_DELAY_SECS, default=DEFAULT_DELAY_SECS):
        vol.Coerce(float),
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})

HARMONY_SYNC_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Harmony platform."""
    host = None
    activity = None

    if CONF_DEVICE_CACHE not in hass.data:
        hass.data[CONF_DEVICE_CACHE] = []

    if discovery_info:
        # Find the discovered device in the list of user configurations
        override = next((c for c in hass.data[CONF_DEVICE_CACHE]
                         if c.get(CONF_NAME) == discovery_info.get(CONF_NAME)),
                        False)

        port = DEFAULT_PORT
        delay_secs = DEFAULT_DELAY_SECS
        if override:
            activity = override.get(ATTR_ACTIVITY)
            delay_secs = override.get(ATTR_DELAY_SECS)
            port = override.get(CONF_PORT, DEFAULT_PORT)

        host = (
            discovery_info.get(CONF_NAME),
            discovery_info.get(CONF_HOST),
            port)

        # Ignore hub name when checking if this hub is known - ip and port only
        if host[1:] in ((h.host, h.port) for h in DEVICES):
            _LOGGER.debug("Discovered host already known: %s", host)
            return
    elif CONF_HOST in config:
        host = (
            config.get(CONF_NAME),
            config.get(CONF_HOST),
            config.get(CONF_PORT),
        )
        activity = config.get(ATTR_ACTIVITY)
        delay_secs = config.get(ATTR_DELAY_SECS)
    else:
        hass.data[CONF_DEVICE_CACHE].append(config)
        return

    name, address, port = host
    _LOGGER.info("Loading Harmony Platform: %s at %s:%s, startup activity: %s",
                 name, address, port, activity)

    harmony_conf_file = hass.config.path(
        '{}{}{}'.format('harmony_', slugify(name), '.conf'))
    try:
        device = HarmonyRemote(
            name, address, port, activity, harmony_conf_file, delay_secs)
        DEVICES.append(device)
        async_add_entities([device])
        register_services(hass)
    except (ValueError, AttributeError):
        raise PlatformNotReady


def register_services(hass):
    """Register all services for harmony devices."""
    hass.services.async_register(
        DOMAIN, SERVICE_SYNC, _sync_service,
        schema=HARMONY_SYNC_SCHEMA)


async def _apply_service(service, service_func, *service_func_args):
    """Handle services to apply."""
    entity_ids = service.data.get('entity_id')

    if entity_ids:
        _devices = [device for device in DEVICES
                    if device.entity_id in entity_ids]
    else:
        _devices = DEVICES

    for device in _devices:
        await service_func(device, *service_func_args)
        device.schedule_update_ha_state(True)


async def _sync_service(service):
    await _apply_service(service, HarmonyRemote.sync)


class HarmonyRemote(remote.RemoteDevice):
    """Remote representation used to control a Harmony device."""

    def __init__(self, name, host, port, activity, out_path, delay_secs):
        """Initialize HarmonyRemote class."""
        import pyharmony.client as harmony_client

        _LOGGER.debug("HarmonyRemote device init started for: %s", name)
        self._name = name
        self.host = host
        self.port = port
        self._state = None
        self._current_activity = None
        self._default_activity = activity
        # self._client = pyharmony.get_client(host, port, self.new_activity)
        self._client = harmony_client.HarmonyClient(host)
        self._config_path = out_path
        self._delay_secs = delay_secs
        _LOGGER.debug("HarmonyRemote device init completed for: %s", name)

    async def async_added_to_hass(self):
        """Complete the initialization."""
        _LOGGER.debug("HarmonyRemote added for: %s", self._name)

        async def shutdown(event):
            """Close connection on shutdown."""
            await self._client.disconnect()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

        _LOGGER.debug("Connecting.")
        await self._client.connect()
        await self._client.get_config()
        if not Path(self._config_path).is_file():
            self.write_config_file()

        # Poll for initial state
        self.new_activity(await self._client.get_current_activity())

    @property
    def name(self):
        """Return the Harmony device's name."""
        return self._name

    @property
    def should_poll(self):
        """Return the fact that we should not be polled."""
        return True

    @property
    def device_state_attributes(self):
        """Add platform specific attributes."""
        return {'current_activity': self._current_activity}

    @property
    def is_on(self):
        """Return False if PowerOff is the current activity, otherwise True."""
        return self._current_activity not in [None, 'PowerOff']

    async def async_update(self):
        """Retrieve current activity from Hub."""
        _LOGGER.debug("Updating Harmony.")
        if not self._client.config:
            await self._client.get_config()

        activity_id = await self._client.get_current_activity()
        activity_name = self._client.get_activity_name(activity_id)
        _LOGGER.debug("%s activity reported as: %s", self._name, activity_name)
        self._current_activity = activity_name
        self._state = bool(self._current_activity != 'PowerOff')
        return

    def new_activity(self, activity_id):
        """Call for updating the current activity."""
        activity_name = self._client.get_activity_name(activity_id)
        _LOGGER.debug("%s activity reported as: %s", self._name, activity_name)
        self._current_activity = activity_name
        self._state = bool(self._current_activity != 'PowerOff')
        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs):
        """Start an activity from the Harmony device."""
        activity = kwargs.get(ATTR_ACTIVITY, self._default_activity)

        if activity:
            activity_id = None
            if activity.isdigit() or activity == '-1':
                _LOGGER.debug("Activity is numeric")
                if self._client.get_activity_name(int(activity)):
                    activity_id = activity

            if not activity_id:
                _LOGGER.debug("Find activity ID based on name")
                activity_id = self._client.get_activity_id(
                    str(activity).strip())

            if not activity_id:
                _LOGGER.error("Activity %s is invalid", activity)
                return

            await self._client.start_activity(activity_id)
            self._state = True
        else:
            _LOGGER.error("No activity specified with turn_on service")

    async def async_turn_off(self, **kwargs):
        """Start the PowerOff activity."""
        await self._client.power_off()

    # pylint: disable=arguments-differ
    async def async_send_command(self, command, **kwargs):
        """Send a list of commands to one device."""
        device = kwargs.get(ATTR_DEVICE)
        if device is None:
            _LOGGER.error("Missing required argument: device")
            return

        device_id = None
        if device.isdigit():
            _LOGGER.debug("Device is numeric")
            if self._client.get_device_name(int(device)):
                device_id = device

        if not device_id:
            _LOGGER.debug("Find device ID based on device name")
            device_id = self._client.get_activity_id(str(device).strip())

        if not device_id:
            _LOGGER.error("Device  %s is invalid", device)
            return

        num_repeats = kwargs.get(ATTR_NUM_REPEATS)
        delay_secs = kwargs.get(ATTR_DELAY_SECS, self._delay_secs)

        for _ in range(num_repeats):
            for single_command in command:
                _LOGGER.debug("Sending command %s", single_command)
                await self._client.send_command(device, single_command)
                await asyncio.sleep(delay_secs)

    async def sync(self):
        """Sync the Harmony device with the web service."""
        _LOGGER.debug("Syncing hub with Harmony servers")
        await self._client.sync()
        await self._client.get_config()
        await self.hass.async_add_executor_job(self.write_config_file)

    def write_config_file(self):
        """Write Harmony configuration file."""
        _LOGGER.debug("Writing hub config to file: %s", self._config_path)
        try:
            with open(self._config_path, 'w+', encoding='utf-8') as file_out:
                json.dump(self._client.json_config, file_out,
                          sort_keys=True, indent=4)
        except IOError as exc:
            _LOGGER.error("Unable to write HUB configuration to %s: %s",
                          self._config_path, exc)
