"""
Exposes regular REST commands as services.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hassio/
"""
import asyncio
from datetime import timedelta
import logging
import os

import voluptuous as vol

from homeassistant.components import SERVICE_CHECK_CONFIG
from homeassistant.const import (
    ATTR_NAME, SERVICE_HOMEASSISTANT_RESTART, SERVICE_HOMEASSISTANT_STOP)
from homeassistant.core import DOMAIN as HASS_DOMAIN
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass
from homeassistant.util.dt import utcnow

from .handler import HassIO
from .http import HassIOView

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'hassio'
DEPENDENCIES = ['http']
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CONF_FRONTEND_REPO = 'development_repo'

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Optional(CONF_FRONTEND_REPO): cv.isdir,
    }),
}, extra=vol.ALLOW_EXTRA)


DATA_HOMEASSISTANT_VERSION = 'hassio_hass_version'
HASSIO_UPDATE_INTERVAL = timedelta(minutes=55)

SERVICE_ADDON_START = 'addon_start'
SERVICE_ADDON_STOP = 'addon_stop'
SERVICE_ADDON_RESTART = 'addon_restart'
SERVICE_ADDON_STDIN = 'addon_stdin'
SERVICE_HOST_SHUTDOWN = 'host_shutdown'
SERVICE_HOST_REBOOT = 'host_reboot'
SERVICE_SNAPSHOT_FULL = 'snapshot_full'
SERVICE_SNAPSHOT_PARTIAL = 'snapshot_partial'
SERVICE_RESTORE_FULL = 'restore_full'
SERVICE_RESTORE_PARTIAL = 'restore_partial'

ATTR_ADDON = 'addon'
ATTR_INPUT = 'input'
ATTR_SNAPSHOT = 'snapshot'
ATTR_ADDONS = 'addons'
ATTR_FOLDERS = 'folders'
ATTR_HOMEASSISTANT = 'homeassistant'
ATTR_PASSWORD = 'password'

SCHEMA_NO_DATA = vol.Schema({})

SCHEMA_ADDON = vol.Schema({
    vol.Required(ATTR_ADDON): cv.slug,
})

SCHEMA_ADDON_STDIN = SCHEMA_ADDON.extend({
    vol.Required(ATTR_INPUT): vol.Any(dict, cv.string)
})

SCHEMA_SNAPSHOT_FULL = vol.Schema({
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_PASSWORD): cv.string,
})

SCHEMA_SNAPSHOT_PARTIAL = SCHEMA_SNAPSHOT_FULL.extend({
    vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
})

SCHEMA_RESTORE_FULL = vol.Schema({
    vol.Required(ATTR_SNAPSHOT): cv.slug,
    vol.Optional(ATTR_PASSWORD): cv.string,
})

SCHEMA_RESTORE_PARTIAL = SCHEMA_RESTORE_FULL.extend({
    vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
    vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
})

MAP_SERVICE_API = {
    SERVICE_ADDON_START: ('/addons/{addon}/start', SCHEMA_ADDON, 60, False),
    SERVICE_ADDON_STOP: ('/addons/{addon}/stop', SCHEMA_ADDON, 60, False),
    SERVICE_ADDON_RESTART:
        ('/addons/{addon}/restart', SCHEMA_ADDON, 60, False),
    SERVICE_ADDON_STDIN:
        ('/addons/{addon}/stdin', SCHEMA_ADDON_STDIN, 60, False),
    SERVICE_HOST_SHUTDOWN: ('/host/shutdown', SCHEMA_NO_DATA, 60, False),
    SERVICE_HOST_REBOOT: ('/host/reboot', SCHEMA_NO_DATA, 60, False),
    SERVICE_SNAPSHOT_FULL:
        ('/snapshots/new/full', SCHEMA_SNAPSHOT_FULL, 300, True),
    SERVICE_SNAPSHOT_PARTIAL:
        ('/snapshots/new/partial', SCHEMA_SNAPSHOT_PARTIAL, 300, True),
    SERVICE_RESTORE_FULL:
        ('/snapshots/{snapshot}/restore/full', SCHEMA_RESTORE_FULL, 300, True),
    SERVICE_RESTORE_PARTIAL:
        ('/snapshots/{snapshot}/restore/partial', SCHEMA_RESTORE_PARTIAL, 300,
         True),
}


@callback
@bind_hass
def get_homeassistant_version(hass):
    """Return latest available Home Assistant version.

    Async friendly.
    """
    return hass.data.get(DATA_HOMEASSISTANT_VERSION)


@callback
@bind_hass
def is_hassio(hass):
    """Return true if hass.io is loaded.

    Async friendly.
    """
    return DOMAIN in hass.config.components


@bind_hass
@asyncio.coroutine
def async_check_config(hass):
    """Check configuration over Hass.io API."""
    hassio = hass.data[DOMAIN]
    result = yield from hassio.check_homeassistant_config()

    if not result:
        return "Hass.io config check API error"
    if result['result'] == "error":
        return result['message']
    return None


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the Hass.io component."""
    try:
        host = os.environ['HASSIO']
    except KeyError:
        _LOGGER.error("Missing HASSIO environment variable.")
        return False

    try:
        os.environ['HASSIO_TOKEN']
    except KeyError:
        _LOGGER.error("Missing HASSIO_TOKEN environment variable.")
        return False

    websession = hass.helpers.aiohttp_client.async_get_clientsession()
    hass.data[DOMAIN] = hassio = HassIO(hass.loop, websession, host)

    if not (yield from hassio.is_connected()):
        _LOGGER.error("Not connected with Hass.io")
        return False

    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    data = yield from store.async_load()

    if data is None:
        data = {}

    refresh_token = None
    if 'hassio_user' in data:
        user = yield from hass.auth.async_get_user(data['hassio_user'])
        if user and user.refresh_tokens:
            refresh_token = list(user.refresh_tokens.values())[0]

    if refresh_token is None:
        user = yield from hass.auth.async_create_system_user('Hass.io')
        refresh_token = yield from hass.auth.async_create_refresh_token(user)
        data['hassio_user'] = user.id
        yield from store.async_save(data)

    # This overrides the normal API call that would be forwarded
    development_repo = config.get(DOMAIN, {}).get(CONF_FRONTEND_REPO)
    if development_repo is not None:
        hass.http.register_static_path(
            '/api/hassio/app',
            os.path.join(development_repo, 'hassio/build'), False)

    hass.http.register_view(HassIOView(host, websession))

    if 'frontend' in hass.config.components:
        yield from hass.components.panel_custom.async_register_panel(
            frontend_url_path='hassio',
            webcomponent_name='hassio-main',
            sidebar_title='Hass.io',
            sidebar_icon='hass:home-assistant',
            js_url='/api/hassio/app/entrypoint.js',
            embed_iframe=True,
        )

    # Temporary. No refresh token tells supervisor to use API password.
    if hass.auth.active:
        token = refresh_token.token
    else:
        token = None

    yield from hassio.update_hass_api(config.get('http', {}), token)

    if 'homeassistant' in config:
        yield from hassio.update_hass_timezone(config['homeassistant'])

    @asyncio.coroutine
    def async_service_handler(service):
        """Handle service calls for Hass.io."""
        api_command = MAP_SERVICE_API[service.service][0]
        data = service.data.copy()
        addon = data.pop(ATTR_ADDON, None)
        snapshot = data.pop(ATTR_SNAPSHOT, None)
        payload = None

        # Pass data to hass.io API
        if service.service == SERVICE_ADDON_STDIN:
            payload = data[ATTR_INPUT]
        elif MAP_SERVICE_API[service.service][3]:
            payload = data

        # Call API
        ret = yield from hassio.send_command(
            api_command.format(addon=addon, snapshot=snapshot),
            payload=payload, timeout=MAP_SERVICE_API[service.service][2]
        )

        if not ret or ret['result'] != "ok":
            _LOGGER.error("Error on Hass.io API: %s", ret['message'])

    for service, settings in MAP_SERVICE_API.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=settings[1])

    @asyncio.coroutine
    def update_homeassistant_version(now):
        """Update last available Home Assistant version."""
        data = yield from hassio.get_homeassistant_info()
        if data:
            hass.data[DATA_HOMEASSISTANT_VERSION] = data['last_version']

        hass.helpers.event.async_track_point_in_utc_time(
            update_homeassistant_version, utcnow() + HASSIO_UPDATE_INTERVAL)

    # Fetch last version
    yield from update_homeassistant_version(None)

    @asyncio.coroutine
    def async_handle_core_service(call):
        """Service handler for handling core services."""
        if call.service == SERVICE_HOMEASSISTANT_STOP:
            yield from hassio.stop_homeassistant()
            return

        error = yield from async_check_config(hass)
        if error:
            _LOGGER.error(error)
            hass.components.persistent_notification.async_create(
                "Config error. See dev-info panel for details.",
                "Config validating", "{0}.check_config".format(HASS_DOMAIN))
            return

        if call.service == SERVICE_HOMEASSISTANT_RESTART:
            yield from hassio.restart_homeassistant()

    # Mock core services
    for service in (SERVICE_HOMEASSISTANT_STOP, SERVICE_HOMEASSISTANT_RESTART,
                    SERVICE_CHECK_CONFIG):
        hass.services.async_register(
            HASS_DOMAIN, service, async_handle_core_service)

    return True
