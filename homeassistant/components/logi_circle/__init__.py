"""
Component for the Swedish weather institute weather service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/smhi/
"""
import asyncio
import logging
import threading
from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP,
                                 CONF_BINARY_SENSORS, CONF_SENSORS,
                                 CONF_MONITORED_CONDITIONS)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.util.dt import as_local

from . import config_flow
from .const import (DOMAIN, DATA_LOGI, SIGNAL_LOGI_CIRCLE_UPDATE,
                    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_API_KEY,
                    CONF_REDIRECT_URI, CONF_CAMERAS, CONF_FFMPEG_ARGUMENTS,
                    LOGI_SENSORS, LOGI_BINARY_SENSORS, DEFAULT_CACHEDB,
                    LOGI_ACTIVITY_KEYS)

REQUIREMENTS = [
    'https://github.com/evanjd/python-logi-circle/archive/'
    'master.zip'
    '#logi_circle==0.2.1'
]

SIGNAL_LOGI_RESTART_SUBSCRIPTION = 'logi_restart_ws'

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(LOGI_BINARY_SENSORS)):
        vol.All(cv.ensure_list, [vol.In(LOGI_BINARY_SENSORS)])
})

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(LOGI_SENSORS)):
        vol.All(cv.ensure_list, [vol.In(LOGI_SENSORS)])
})

CAMERA_SCHEMA = vol.Schema({
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string
})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
        vol.Schema({
            vol.Required(CONF_CLIENT_ID): cv.string,
            vol.Required(CONF_CLIENT_SECRET): cv.string,
            vol.Required(CONF_API_KEY): cv.string,
            vol.Required(CONF_REDIRECT_URI): cv.string,
            vol.Optional(CONF_BINARY_SENSORS, default={}):
                BINARY_SENSOR_SCHEMA,
            vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
            vol.Optional(CONF_CAMERAS, default={}): CAMERA_SCHEMA,
        })
    },
    extra=vol.ALLOW_EXTRA,
)


def logi_circle_update_event_broker(hass, subscription):
    """Dispatch SIGNAL_LOGI_CIRCLE_UPDATE to devices when
       API wrapper has processed a WS frame."""

    async def async_start(hass, subscription):
        auto_restart_subscription = True
        await subscription.open()
        while hass.is_running and subscription.opened:
            await subscription.get_next_event()

            if not hass.is_running or subscription.invalidated:
                auto_restart_subscription = False
                break

            async_dispatcher_send(hass, SIGNAL_LOGI_CIRCLE_UPDATE)

        if auto_restart_subscription:
            _LOGGER.warning(
                "WS connection closed unexpectedly. Reopening in 10 secs.")
            await asyncio.sleep(10)
            async_dispatcher_send(hass, SIGNAL_LOGI_RESTART_SUBSCRIPTION)

    asyncio.new_event_loop().run_until_complete(
        async_start(hass, subscription))


def parse_logi_activity(activity):
    """Read props from Activity instance."""

    activity_state_props = {}
    for prop in LOGI_ACTIVITY_KEYS:
        prop_value = getattr(activity or {}, prop[1], None)

        if isinstance(prop_value, datetime):
            activity_state_props[prop[0]] = as_local(
                prop_value)
        elif isinstance(prop_value, timedelta):
            activity_state_props[prop[0]] = prop_value.total_seconds()
        else:
            activity_state_props[prop[0]] = prop_value

    return activity_state_props


async def async_setup(hass, config):
    """Set up configured Logi Circle component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    config_flow.register_flow_implementation(
        hass,
        DOMAIN,
        client_id=conf[CONF_CLIENT_ID],
        client_secret=conf[CONF_CLIENT_SECRET],
        api_key=conf[CONF_API_KEY],
        redirect_uri=conf[CONF_REDIRECT_URI],
        sensors=conf[CONF_SENSORS],
        binary_sensors=conf[CONF_BINARY_SENSORS],
        cameras=conf[CONF_CAMERAS])

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={'source': config_entries.SOURCE_IMPORT},
        ))

    return True


async def async_setup_entry(hass, entry):
    """Set up Logi Circle from a config entry."""
    from logi_circle import LogiCircle

    logi_circle = LogiCircle(
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        api_key=entry.data[CONF_API_KEY],
        redirect_uri=entry.data[CONF_REDIRECT_URI],
        cache_file=DEFAULT_CACHEDB
    )

    if not logi_circle.authorized:
        return False

    await logi_circle.synchronize_cameras()

    hass.data[DATA_LOGI] = logi_circle
    for component in 'camera', 'sensor', 'binary_sensor':
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            entry, component))

    subscription = None

    async def start_up(event=None):
        """Start Logi update event listener."""
        subscription = await logi_circle.subscribe(
            ['accessory_settings_changed',
             'activity_created',
             'activity_updated',
             'activity_finished'])

        threading.Thread(
            name='Logi update listener',
            target=logi_circle_update_event_broker,
            args=(hass, subscription)
        ).start()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_up)
    async_unsub_dispatcher_connect = (
        async_dispatcher_connect(hass, SIGNAL_LOGI_RESTART_SUBSCRIPTION,
                                 start_up))

    async def shut_down(event=None):
        """Stop Logi Circle update event listener."""
        async_unsub_dispatcher_connect()
        if subscription:
            subscription.invalidate()
            await subscription.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shut_down)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    for component in 'camera', 'sensor', 'binary_sensor':
        await hass.config_entries.async_forward_entry_unload(
            entry, component)

    logi_circle = hass.data.pop(DATA_LOGI)

    # Tell API wrapper to close all aiohttp sessions, invalidate WS connections
    # and clear all locally cached tokens
    await logi_circle.auth_provider.clear_authorization()

    return True
