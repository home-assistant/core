"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from datetime import timedelta
import logging
import socket

import voluptuous as vol

from homeassistant.components.discovery import SERVICE_FREEBOX
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['aiofreepybox==0.0.8']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'freebox'
DATA_FREEBOX = DOMAIN
DATA_FREEBOX_SENSOR = 'freebox_sensor'
UPDATE_INTERVAL = timedelta(seconds=30)
FREEBOX_CONFIG_FILE = 'freebox.conf'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Freebox component."""
    conf = config.get(DOMAIN)

    async def discovery_dispatch(service, discovery_info):
        if conf is None:
            host = discovery_info.get('properties', {}).get('api_domain')
            port = discovery_info.get('properties', {}).get('https_port')
            _LOGGER.info("Discovered Freebox server: %s:%s", host, port)
            fbx = await get_freebox_connection(hass, config, host, port)
            await async_setup_freebox(hass, config, fbx)

    discovery.async_listen(hass, SERVICE_FREEBOX, discovery_dispatch)

    if conf is not None:
        host = conf.get(CONF_HOST)
        port = conf.get(CONF_PORT)
        fbx = await get_freebox_connection(hass, config, host, port)
        await async_setup_freebox(hass, config, fbx)

    return True


async def get_freebox_connection(hass, config, host, port):
    """Connect to the router and return connection object."""
    from aiofreepybox import Freepybox
    from aiofreepybox.exceptions import HttpRequestError

    app_desc = {
        'app_id': 'hass',
        'app_name': 'Home Assistant',
        'app_version': '0.65',
        'device_name': socket.gethostname()
        }

    token_file = hass.config.path(FREEBOX_CONFIG_FILE)
    api_version = 'v4'

    fbx = Freepybox(
        app_desc=app_desc,
        token_file=token_file,
        api_version=api_version)

    try:
        await fbx.open(host, port)
    except HttpRequestError:
        _LOGGER.exception('Failed to connect to Freebox')
    return fbx


async def async_setup_freebox(hass, config, fbx):
    """Start up the Freebox component platforms."""
    await async_update_sensor_data(hass, fbx)

    async def close_fbx(event):
        """Close Freebox connection on HA Stop."""
        await fbx.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_fbx)

    async def async_update_freebox(now):
        """Call update of datas on time interval."""
        await async_update_sensor_data(hass, fbx)

    hass.data[DATA_FREEBOX] = fbx

    async_track_time_interval(hass, async_update_freebox, UPDATE_INTERVAL)

    hass.async_create_task(discovery.async_load_platform(
        hass, 'sensor', DOMAIN, {}, config))
    hass.async_create_task(discovery.async_load_platform(
        hass, 'switch', DOMAIN, {}, config))
    hass.async_create_task(discovery.async_load_platform(
        hass, 'device_tracker', DOMAIN, {}, config))


async def async_update_sensor_data(hass, fbx):
    """Update sensors datas shared object."""
    hass.data[DATA_FREEBOX_SENSOR] = await fbx.connection.get_status()
