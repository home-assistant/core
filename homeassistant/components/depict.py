"""
Support for controlling Depict digital art frames.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/depict/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send

REQUIREMENTS = ['depict-control==1.0']

_LOGGER = logging.getLogger(__name__)

ATTR_VALUE = 'value'
DATA_DEPICT = 'depict'
DOMAIN = 'depict'
SIGNAL_SET_CONTRAST = 'depict.set_contrast'

AUTODETECT_SCHEMA = vol.Schema({})

FRAME_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
})

FRAMES_SCHEMA = vol.Schema([FRAME_SCHEMA])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Any(AUTODETECT_SCHEMA, FRAMES_SCHEMA),
}, extra=vol.ALLOW_EXTRA)

SERVICE_SET_CONTRAST_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    ATTR_VALUE: cv.byte,
})


async def async_setup(hass, config):
    """Set up the depict component."""
    from depict_control import Frame
    frames = hass.data.setdefault(DATA_DEPICT, {})
    frame_configs = config.get(DOMAIN)
    session = async_get_clientsession(hass)

    async def add_frame(host, name=None):
        """Add platforms for a single frame with the given hostname."""
        frame = await Frame.connect(session, host)
        if name is None:
            name = frame.name
        frames[name] = frame
        _LOGGER.debug("Connected to %s at %s", name, host)

        hass.async_create_task(async_load_platform(
            hass, 'light', DOMAIN, {
                CONF_NAME: name,
            }, config))
        hass.async_create_task(async_load_platform(
            hass, 'media_player', DOMAIN, {
                CONF_NAME: name,
            }, config
        ))

    if isinstance(frame_configs, dict):  # AUTODETECT_SCHEMA
        for ip_address in await Frame.find_frame_ips(session):
            await add_frame(ip_address)
    else:  # FRAMES_SCHEMA
        for conf in frame_configs:
            await add_frame(conf[CONF_HOST], conf[CONF_NAME])

    async def close_frames(*args):
        """Close all frame objects."""
        tasks = [frame.close() for frame in frames.values()]
        if tasks:
            await asyncio.wait(tasks)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_frames)

    async def handle_set_contrast(call):
        async_dispatcher_send(hass, SIGNAL_SET_CONTRAST, call.data)

    hass.services.async_register(
        DOMAIN,
        'set_contrast',
        handle_set_contrast,
        schema=SERVICE_SET_CONTRAST_SCHEMA)

    return True
