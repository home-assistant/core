"""
Component for the Swedish weather institute weather service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/smhi/
"""
import asyncio
import logging
import threading

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.camera import CAMERA_SERVICE_SCHEMA, ATTR_FILENAME
from homeassistant.const import (EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP)
from homeassistant.core import callback as async_callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.dt import as_local, parse_datetime, utc_from_timestamp

# Have to import for config_flow to work even if they are not used here
from . import config_flow
from .const import (DOMAIN, DATA_LOGI, DEFAULT_NAME, SIGNAL_LOGI_CIRCLE_UPDATE,
                    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_API_KEY, CONF_REDIRECT_URI,
                    CONF_ATTRIBUTION)

REQUIREMENTS = [
    'https://github.com/evanjd/python-logi-circle/archive/'
    'master.zip'
    '#logi_circle==0.2.1'
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
        vol.Schema({
            vol.Required(CONF_CLIENT_ID): cv.string,
            vol.Required(CONF_CLIENT_SECRET): cv.string,
            vol.Required(CONF_API_KEY): cv.string,
            vol.Required(CONF_REDIRECT_URI): cv.string,
        })
    },
    extra=vol.ALLOW_EXTRA,
)


async def logi_circle_update_event_broker(hass, subscription):
    """Dispatch SIGNAL_LOGI_CIRCLE_UPDATE to devices when API wrapper has processed a WS frame."""

    await subscription.open()
    while hass.is_running and subscription.is_open:
        await subscription.get_next_event()

        if not hass.is_running:
            break

        async_dispatcher_send(hass, SIGNAL_LOGI_CIRCLE_UPDATE)


async def async_setup(hass, config):
    """Set up configured Logi Circle component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    config_flow.register_flow_implementation(
        hass,
        DOMAIN,
        conf[CONF_CLIENT_ID],
        conf[CONF_CLIENT_SECRET],
        conf[CONF_API_KEY],
        conf[CONF_REDIRECT_URI])

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': config_entries.SOURCE_IMPORT},
        ))

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Logi Circle from a config entry."""
    from logi_circle import LogiCircle

    logi_circle = LogiCircle(
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        api_key=entry.data[CONF_API_KEY],
        redirect_uri=entry.data[CONF_REDIRECT_URI]
    )

    if not logi_circle.authorized:
        return False

    hass.data[DATA_LOGI] = logi_circle
    for component in 'camera', 'sensor', 'binary_sensor':
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            entry, component))

    event_subscription = await logi_circle.subscribe(['accessory_settings_changed',
                                                      'activity_created',
                                                      'activity_updated',
                                                      'activity_finished'])

    async def start_up(event):
        """Start Logi update event listener."""
        hass.async_create_task(
            logi_circle_update_event_broker(hass, event_subscription))

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_up)

    async def shut_down(event):
        """Stop Logi Circle update event listener."""
        await event_subscription.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shut_down)

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    print('TODO!')
