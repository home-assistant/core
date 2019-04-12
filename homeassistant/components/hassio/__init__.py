"""Support for Hass.io."""
from datetime import timedelta
import logging
import os

import voluptuous as vol

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.homeassistant import SERVICE_CHECK_CONFIG
import homeassistant.config as conf_util
from homeassistant.const import (
    ATTR_NAME, SERVICE_HOMEASSISTANT_RESTART, SERVICE_HOMEASSISTANT_STOP)
from homeassistant.core import DOMAIN as HASS_DOMAIN, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import bind_hass
from homeassistant.util.dt import utcnow

from .auth import async_setup_auth
from .discovery import async_setup_discovery
from .handler import HassIO, HassioAPIError
from .http import HassIOView
from .ingress import async_setup_ingress

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


async def async_setup(hass, config):
    """Set up the Hass.io component."""
    # Check local setup
    for env in ('HASSIO', 'HASSIO_TOKEN'):
        if os.environ.get(env):
            continue
        _LOGGER.error("Missing %s environment variable.", env)
        return False

    host = os.environ['HASSIO']
    websession = hass.helpers.aiohttp_client.async_get_clientsession()
    hass.data[DOMAIN] = hassio = HassIO(hass.loop, websession, host)

    if not await hassio.is_connected():
        _LOGGER.warning("Not connected with Hass.io / system to busy!")

    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()

    if data is None:
        data = {}

    refresh_token = None
    if 'hassio_user' in data:
        user = await hass.auth.async_get_user(data['hassio_user'])
        if user and user.refresh_tokens:
            refresh_token = list(user.refresh_tokens.values())[0]

            # Migrate old hass.io users to be admin.
            if not user.is_admin:
                await hass.auth.async_update_user(
                    user, group_ids=[GROUP_ID_ADMIN])

    if refresh_token is None:
        user = await hass.auth.async_create_system_user(
            'Hass.io', [GROUP_ID_ADMIN])
        refresh_token = await hass.auth.async_create_refresh_token(user)
        data['hassio_user'] = user.id
        await store.async_save(data)

    # This overrides the normal API call that would be forwarded
    development_repo = config.get(DOMAIN, {}).get(CONF_FRONTEND_REPO)
    if development_repo is not None:
        hass.http.register_static_path(
            '/api/hassio/app',
            os.path.join(development_repo, 'hassio/build'), False)

    hass.http.register_view(HassIOView(host, websession))

    if 'frontend' in hass.config.components:
        await hass.components.panel_custom.async_register_panel(
            frontend_url_path='hassio',
            webcomponent_name='hassio-main',
            sidebar_title='Hass.io',
            sidebar_icon='hass:home-assistant',
            js_url='/api/hassio/app/entrypoint.js',
            embed_iframe=True,
            require_admin=True,
        )

    await hassio.update_hass_api(config.get('http', {}), refresh_token.token)

    if 'homeassistant' in config:
        await hassio.update_hass_timezone(config['homeassistant'])

    async def async_service_handler(service):
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
        try:
            await hassio.send_command(
                api_command.format(addon=addon, snapshot=snapshot),
                payload=payload, timeout=MAP_SERVICE_API[service.service][2]
            )
        except HassioAPIError as err:
            _LOGGER.error("Error on Hass.io API: %s", err)

    for service, settings in MAP_SERVICE_API.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=settings[1])

    async def update_homeassistant_version(now):
        """Update last available Home Assistant version."""
        try:
            data = await hassio.get_homeassistant_info()
            hass.data[DATA_HOMEASSISTANT_VERSION] = data['last_version']
        except HassioAPIError as err:
            _LOGGER.warning("Can't read last version: %s", err)

        hass.helpers.event.async_track_point_in_utc_time(
            update_homeassistant_version, utcnow() + HASSIO_UPDATE_INTERVAL)

    # Fetch last version
    await update_homeassistant_version(None)

    async def async_handle_core_service(call):
        """Service handler for handling core services."""
        if call.service == SERVICE_HOMEASSISTANT_STOP:
            await hassio.stop_homeassistant()
            return

        try:
            errors = await conf_util.async_check_ha_config_file(hass)
        except HomeAssistantError:
            return

        if errors:
            _LOGGER.error(errors)
            hass.components.persistent_notification.async_create(
                "Config error. See dev-info panel for details.",
                "Config validating", "{0}.check_config".format(HASS_DOMAIN))
            return

        if call.service == SERVICE_HOMEASSISTANT_RESTART:
            await hassio.restart_homeassistant()

    # Mock core services
    for service in (SERVICE_HOMEASSISTANT_STOP, SERVICE_HOMEASSISTANT_RESTART,
                    SERVICE_CHECK_CONFIG):
        hass.services.async_register(
            HASS_DOMAIN, service, async_handle_core_service)

    # Init discovery Hass.io feature
    async_setup_discovery(hass, hassio, config)

    # Init auth Hass.io feature
    async_setup_auth(hass)

    # Init ingress Hass.io feature
    async_setup_ingress(hass, host)

    return True
