"""
Support for Telldus Live.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tellduslive/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from . import config_flow  # noqa  pylint_disable=unused-import
from .const import (
    CONF_HOST, CONF_UPDATE_INTERVAL, DOMAIN, KEY_HOST, MIN_UPDATE_INTERVAL,
    NOT_SO_PRIVATE_KEY, PUBLIC_KEY, SCAN_INTERVAL, SIGNAL_UPDATE_ENTITY,
    TELLDUS_DISCOVERY_NEW)

APPLICATION_NAME = 'Home Assistant'

REQUIREMENTS = ['tellduslive==0.10.6']

DATA_CONFIG_ENTRY_LOCK = 'tellduslive_config_entry_lock'
CONFIG_ENTRY_IS_SETUP = 'telldus_config_entry_is_setup'

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


async def async_setup_entry(hass, entry):
    """Create a tellduslive session."""
    from tellduslive import Session
    conf = entry.data

    if KEY_HOST in conf:
        session = Session(**conf)
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

    dev_reg = await hass.helpers.device_registry.async_get_registry()
    for hub in await client.get_hubs():
        _LOGGER.debug("Connected hub %s", hub['name'])
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={('IP', hub['ip'])},
            identifiers={(DOMAIN, hub['id'])},
            manufacturer='Telldus',
            name=hub['name'],
            model=hub['type'],
            sw_version=hub['version'],
        )

    await client.update()

    global SCAN_INTERVAL
    SCAN_INTERVAL = hass.data.get("{}_{}".format(DOMAIN, CONF_UPDATE_INTERVAL),
                                  SCAN_INTERVAL)
    _LOGGER.debug('Update interval %s', SCAN_INTERVAL)
    async_track_time_interval(hass, client.update, SCAN_INTERVAL)

    return True


async def async_setup(hass, config):
    """Set up the Telldus Live component."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': config_entries.SOURCE_IMPORT},
            data={KEY_HOST: config.get(DOMAIN, {}).get(CONF_HOST)}))
    return True


class TelldusLiveClient:
    """Get the latest data and update the states."""

    def __init__(self, hass, config, session):
        """Initialize the Tellus data object."""
        self._known_devices = set()
        self.entities_info = {}

        self._hass = hass
        self._config = config
        self._client = session

    async def get_hubs(self):
        """Return hubs registered for the user."""
        return self._client.get_clients()

    async def update(self, *args):
        """Periodically poll the servers for current state."""
        _LOGGER.debug('Updating')
        if not self._client.update():
            _LOGGER.warning('Failed request')

        def identify_device(device):
            """Find out what type of HA component to create."""
            from tellduslive import (DIM, UP, TURNON)
            if device.methods & DIM:
                return 'light'
            if device.methods & UP:
                return 'cover'
            if device.methods & TURNON:
                return 'switch'
            if device.methods == 0:
                return 'binary_sensor'
            _LOGGER.warning(
                "Unidentified device type (methods: %d)", device.methods)
            return 'switch'

        async def discover(device_id, component):
            """Discover the component."""
            config_entries_key = '{}.{}'.format(component, DOMAIN)
            async with self._hass.data[DATA_CONFIG_ENTRY_LOCK]:
                if config_entries_key not in self._hass.data[
                        CONFIG_ENTRY_IS_SETUP]:
                    await self._hass.config_entries.async_forward_entry_setup(
                        self._config, component)
                    self._hass.data[CONFIG_ENTRY_IS_SETUP].add(
                        config_entries_key)

            async_dispatcher_send(
                self._hass, TELLDUS_DISCOVERY_NEW.format(component, DOMAIN),
                device_id)

        for device in self._client.devices:
            if device.device_id in self._known_devices:
                continue
            if device.is_sensor:
                for item in device.items:
                    await discover((device.device_id, item.name, item.scale),
                                   'sensor')
            else:
                # Sensors already have this information.
                self.entities_info.update({
                    device.device_id:
                    await self._hass.async_add_executor_job(device.info)
                })
                await discover(device.device_id, identify_device(device))
            self._known_devices.add(device.device_id)
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY)

    def device(self, device_id):
        """Return device representation."""
        return self._client.device(device_id)

    def is_available(self, device_id):
        """Return device availability."""
        return device_id in self._client.device_ids
