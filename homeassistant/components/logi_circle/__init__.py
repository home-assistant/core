"""
Component for the Swedish weather institute weather service.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/smhi/
"""
import asyncio
from datetime import datetime, timedelta
import logging
import threading

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_BINARY_SENSORS, CONF_MONITORED_CONDITIONS, CONF_SENSORS,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.util.dt import as_local

from . import config_flow
from .const import (
    CONF_API_KEY, CONF_CAMERAS, CONF_CLIENT_ID, CONF_CLIENT_SECRET,
    CONF_FFMPEG_ARGUMENTS, CONF_REDIRECT_URI, DATA_LOGI, DEFAULT_CACHEDB,
    DOMAIN, LOGI_ACTIVITY_KEYS, LOGI_BINARY_SENSORS, LOGI_SENSORS,
    SIGNAL_LOGI_CIRCLE_UPDATE)

REQUIREMENTS = ['logi_circle==0.2.0']

SIGNAL_LOGI_RESTART_SUBSCRIPTION = 'logi_restart_ws'

NOTIFICATION_ID = 'logi_circle_notification'
NOTIFICATION_TITLE = 'Logi Circle Setup'

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 15  # seconds

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


def logi_circle_update_event_broker(hass, logi_circle):
    """
    Dispatch SIGNAL_LOGI_CIRCLE_UPDATE to devices.

    Fired after API wrapper processes a WS frame.
    """
    async def async_start(hass, logi_circle):
        auto_restart_subscription = True

        while auto_restart_subscription and hass.is_running:
            subscription_coro = logi_circle.subscribe(
                ['accessory_settings_changed',
                 'activity_created',
                 'activity_updated',
                 'activity_finished'])
            subscription = run_coroutine_threadsafe(
                subscription_coro, hass.loop).result()

            await subscription.open()
            while hass.is_running and subscription.opened:
                await subscription.get_next_event()

                if not hass.is_running or subscription.invalidated:
                    auto_restart_subscription = False
                    break

                async_dispatcher_send(hass, SIGNAL_LOGI_CIRCLE_UPDATE)

            if auto_restart_subscription:
                _LOGGER.warning("WS connection closed unexpectedly, "
                                "reopening in 10 secs")
                await asyncio.sleep(10)

    asyncio.new_event_loop().run_until_complete(
        async_start(hass, logi_circle))


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
    from logi_circle.exception import AuthorizationFailed
    from aiohttp.client_exceptions import ClientResponseError

    logi_circle = LogiCircle(
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        api_key=entry.data[CONF_API_KEY],
        redirect_uri=entry.data[CONF_REDIRECT_URI],
        cache_file=DEFAULT_CACHEDB
    )

    if not logi_circle.authorized:
        hass.components.persistent_notification.create(
            "Error: The cached access tokens are missing from {}.<br />"
            "Please unload then re-add the Logi Circle integration to resolve."
            ''.format(DEFAULT_CACHEDB),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    try:
        # Ensure the cameras property returns the same Camera object for all
        # devices. Performs implicit login and session validation.
        with async_timeout.timeout(_TIMEOUT, loop=hass.loop):
            await logi_circle.synchronize_cameras()
    except AuthorizationFailed:
        hass.components.persistent_notification.create(
            "Error: Failed to obtain an access token from the cached "
            "refresh token.<br />"
            "Token may have expired or been revoked.<br />"
            "Please unload then re-add the Logi Circle integration to resolve",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    except asyncio.TimeoutError:
        # The TimeoutError exception object returns nothing when casted to a
        # string, so we'll handle it separately.
        err = "{}s timeout exceeded when connecting to Logi Circle API".format(
            _TIMEOUT)
        hass.components.persistent_notification.create(
            "Error: {}<br />"
            "You will need to restart hass after fixing."
            ''.format(err),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False
    except ClientResponseError as ex:
        hass.components.persistent_notification.create(
            "Error: {}<br />"
            "You will need to restart hass after fixing."
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    hass.data[DATA_LOGI] = logi_circle
    for component in 'camera', 'sensor', 'binary_sensor':
        hass.async_create_task(hass.config_entries.async_forward_entry_setup(
            entry, component))

    async def start_up(event=None):
        """Start Logi update event listener."""
        threading.Thread(
            name='Logi update listener',
            target=logi_circle_update_event_broker,
            args=(hass, logi_circle)
        ).start()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_up)

    async def shut_down(event=None):
        """Stop Logi Circle update event listener."""
        await logi_circle.auth_provider.close()

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
