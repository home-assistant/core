"""
Support for Telldus Live.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tellduslive/
"""
import asyncio
from datetime import timedelta
from functools import partial
import logging

import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from . import config_flow  # noqa  pylint_disable=unused-import
from .const import (
    CONF_HOST, CONF_UPDATE_INTERVAL, DOMAIN, KEY_HOST, KEY_SCAN_INTERVAL,
    KEY_SESSION, MIN_UPDATE_INTERVAL, NOT_SO_PRIVATE_KEY, PUBLIC_KEY,
    SCAN_INTERVAL, SIGNAL_UPDATE_ENTITY, TELLDUS_DISCOVERY_NEW)

APPLICATION_NAME = 'Home Assistant'

REQUIREMENTS = ['tellduslive==0.10.8']

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
        vol.Schema({
            vol.Optional(CONF_HOST, default=DOMAIN):
            cv.string,
            vol.Optional(CONF_UPDATE_INTERVAL, default=SCAN_INTERVAL):
            (vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL)))
        }),
    },
    extra=vol.ALLOW_EXTRA,
)

DATA_CONFIG_ENTRY_LOCK = 'tellduslive_config_entry_lock'
CONFIG_ENTRY_IS_SETUP = 'telldus_config_entry_is_setup'

INTERVAL_TRACKER = '{}_INTERVAL'.format(DOMAIN)


async def async_setup_entry(hass, entry):
    """Create a tellduslive session."""
    from tellduslive import Session
    conf = entry.data[KEY_SESSION]

    if KEY_HOST in conf:
        # Session(**conf) does blocking IO when
        # communicating with local devices.
        session = await hass.async_add_executor_job(partial(Session, **conf))
    else:
        session = Session(
            PUBLIC_KEY,
            NOT_SO_PRIVATE_KEY,
            application=APPLICATION_NAME,
            **conf,
        )

    if not session.is_authorized:
        _LOGGER.error('Authentication Error')
        return False

    hass.data[DATA_CONFIG_ENTRY_LOCK] = asyncio.Lock()
    hass.data[CONFIG_ENTRY_IS_SETUP] = set()

    client = TelldusLiveClient(hass, entry, session)
    hass.data[DOMAIN] = client
    await async_add_hubs(hass, client, entry.entry_id)
    hass.async_create_task(client.update())

    interval = timedelta(seconds=entry.data[KEY_SCAN_INTERVAL])
    _LOGGER.debug('Update interval %s', interval)
    hass.data[INTERVAL_TRACKER] = async_track_time_interval(
        hass, client.update, interval)

    return True


async def async_add_hubs(hass, client, entry_id):
    """Add the hubs associated with the current client to device_registry."""
    dev_reg = await hass.helpers.device_registry.async_get_registry()
    for hub in await client.async_get_hubs():
        _LOGGER.debug("Connected hub %s", hub['name'])
        dev_reg.async_get_or_create(
            config_entry_id=entry_id,
            identifiers={(DOMAIN, hub['id'])},
            manufacturer='Telldus',
            name=hub['name'],
            model=hub['type'],
            sw_version=hub['version'],
        )


async def async_setup(hass, config):
    """Set up the Telldus Live component."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': config_entries.SOURCE_IMPORT},
            data={
                KEY_HOST: config[DOMAIN].get(CONF_HOST),
                KEY_SCAN_INTERVAL: config[DOMAIN].get(CONF_UPDATE_INTERVAL),
            }))
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    interval_tracker = hass.data.pop(INTERVAL_TRACKER)
    interval_tracker()
    await asyncio.wait([
        hass.config_entries.async_forward_entry_unload(config_entry, component)
        for component in hass.data.pop(CONFIG_ENTRY_IS_SETUP)
    ])
    del hass.data[DOMAIN]
    del hass.data[DATA_CONFIG_ENTRY_LOCK]
    return True


class TelldusLiveClient:
    """Get the latest data and update the states."""

    def __init__(self, hass, config_entry, session):
        """Initialize the Tellus data object."""
        self._known_devices = set()
        self._device_infos = {}

        self._hass = hass
        self._config_entry = config_entry
        self._client = session

    async def async_get_hubs(self):
        """Return hubs registered for the user."""
        clients = await self._hass.async_add_executor_job(
            self._client.get_clients)
        return clients or []

    def device_info(self, device_id):
        """Return device info."""
        return self._device_infos.get(device_id)

    @staticmethod
    def identify_device(device):
        """Find out what type of HA component to create."""
        if device.is_sensor:
            return 'sensor'
        from tellduslive import (DIM, UP, TURNON)
        if device.methods & DIM:
            return 'light'
        if device.methods & UP:
            return 'cover'
        if device.methods & TURNON:
            return 'switch'
        if device.methods == 0:
            return 'binary_sensor'
        _LOGGER.warning("Unidentified device type (methods: %d)",
                        device.methods)
        return 'switch'

    async def _discover(self, device_id):
        """Discover the component."""
        device = self._client.device(device_id)
        component = self.identify_device(device)
        self._device_infos.update({
            device_id:
            await self._hass.async_add_executor_job(device.info)
        })
        async with self._hass.data[DATA_CONFIG_ENTRY_LOCK]:
            if component not in self._hass.data[CONFIG_ENTRY_IS_SETUP]:
                await self._hass.config_entries.async_forward_entry_setup(
                    self._config_entry, component)
                self._hass.data[CONFIG_ENTRY_IS_SETUP].add(component)
        device_ids = []
        if device.is_sensor:
            for item in device.items:
                device_ids.append((device.device_id, item.name, item.scale))
        else:
            device_ids.append(device_id)
        for _id in device_ids:
            async_dispatcher_send(
                self._hass, TELLDUS_DISCOVERY_NEW.format(component, DOMAIN),
                _id)

    async def update(self, *args):
        """Periodically poll the servers for current state."""
        if not await self._hass.async_add_executor_job(self._client.update):
            _LOGGER.warning('Failed request')

        dev_ids = {dev.device_id for dev in self._client.devices}
        new_devices = dev_ids - self._known_devices
        # just await each discover as `gather` use up all HTTPAdapter pools
        for d_id in new_devices:
            await self._discover(d_id)
        self._known_devices |= new_devices
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY)

    def device(self, device_id):
        """Return device representation."""
        return self._client.device(device_id)

    def is_available(self, device_id):
        """Return device availability."""
        return device_id in self._client.device_ids
