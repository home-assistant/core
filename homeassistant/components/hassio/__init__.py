"""Support for Hass.io."""
from datetime import timedelta
import logging
import os

import voluptuous as vol

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components.homeassistant import SERVICE_CHECK_CONFIG
import homeassistant.config as conf_util
from homeassistant.const import (
    ATTR_NAME,
    EVENT_CORE_CONFIG_UPDATE,
    SERVICE_HOMEASSISTANT_RESTART,
    SERVICE_HOMEASSISTANT_STOP,
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass
from homeassistant.util.dt import utcnow

from .addon_panel import async_setup_addon_panel
from .auth import async_setup_auth_view
from .discovery import async_setup_discovery_view
from .handler import HassIO, HassioAPIError
from .http import HassIOView
from .ingress import async_setup_ingress_view

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hassio"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

CONF_FRONTEND_REPO = "development_repo"

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.Schema({vol.Optional(CONF_FRONTEND_REPO): cv.isdir})},
    extra=vol.ALLOW_EXTRA,
)


DATA_INFO = "hassio_info"
DATA_HOST_INFO = "hassio_host_info"
HASSIO_UPDATE_INTERVAL = timedelta(minutes=55)

SERVICE_ADDON_START = "addon_start"
SERVICE_ADDON_STOP = "addon_stop"
SERVICE_ADDON_RESTART = "addon_restart"
SERVICE_ADDON_STDIN = "addon_stdin"
SERVICE_HOST_SHUTDOWN = "host_shutdown"
SERVICE_HOST_REBOOT = "host_reboot"
SERVICE_SNAPSHOT_FULL = "snapshot_full"
SERVICE_SNAPSHOT_PARTIAL = "snapshot_partial"
SERVICE_RESTORE_FULL = "restore_full"
SERVICE_RESTORE_PARTIAL = "restore_partial"

ATTR_ADDON = "addon"
ATTR_INPUT = "input"
ATTR_SNAPSHOT = "snapshot"
ATTR_ADDONS = "addons"
ATTR_FOLDERS = "folders"
ATTR_HOMEASSISTANT = "homeassistant"
ATTR_PASSWORD = "password"

SCHEMA_NO_DATA = vol.Schema({})

SCHEMA_ADDON = vol.Schema({vol.Required(ATTR_ADDON): cv.slug})

SCHEMA_ADDON_STDIN = SCHEMA_ADDON.extend(
    {vol.Required(ATTR_INPUT): vol.Any(dict, cv.string)}
)

SCHEMA_SNAPSHOT_FULL = vol.Schema(
    {vol.Optional(ATTR_NAME): cv.string, vol.Optional(ATTR_PASSWORD): cv.string}
)

SCHEMA_SNAPSHOT_PARTIAL = SCHEMA_SNAPSHOT_FULL.extend(
    {
        vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
    }
)

SCHEMA_RESTORE_FULL = vol.Schema(
    {vol.Required(ATTR_SNAPSHOT): cv.slug, vol.Optional(ATTR_PASSWORD): cv.string}
)

SCHEMA_RESTORE_PARTIAL = SCHEMA_RESTORE_FULL.extend(
    {
        vol.Optional(ATTR_HOMEASSISTANT): cv.boolean,
        vol.Optional(ATTR_FOLDERS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ADDONS): vol.All(cv.ensure_list, [cv.string]),
    }
)

MAP_SERVICE_API = {
    SERVICE_ADDON_START: ("/addons/{addon}/start", SCHEMA_ADDON, 60, False),
    SERVICE_ADDON_STOP: ("/addons/{addon}/stop", SCHEMA_ADDON, 60, False),
    SERVICE_ADDON_RESTART: ("/addons/{addon}/restart", SCHEMA_ADDON, 60, False),
    SERVICE_ADDON_STDIN: ("/addons/{addon}/stdin", SCHEMA_ADDON_STDIN, 60, False),
    SERVICE_HOST_SHUTDOWN: ("/host/shutdown", SCHEMA_NO_DATA, 60, False),
    SERVICE_HOST_REBOOT: ("/host/reboot", SCHEMA_NO_DATA, 60, False),
    SERVICE_SNAPSHOT_FULL: ("/snapshots/new/full", SCHEMA_SNAPSHOT_FULL, 300, True),
    SERVICE_SNAPSHOT_PARTIAL: (
        "/snapshots/new/partial",
        SCHEMA_SNAPSHOT_PARTIAL,
        300,
        True,
    ),
    SERVICE_RESTORE_FULL: (
        "/snapshots/{snapshot}/restore/full",
        SCHEMA_RESTORE_FULL,
        300,
        True,
    ),
    SERVICE_RESTORE_PARTIAL: (
        "/snapshots/{snapshot}/restore/partial",
        SCHEMA_RESTORE_PARTIAL,
        300,
        True,
    ),
}


@bind_hass
async def async_get_addon_info(hass: HomeAssistantType, addon_id: str) -> dict:
    """Return add-on info.

    The addon_id is a snakecased concatenation of the 'repository' value
    found in the add-on info and the 'slug' value found in the add-on config.json.
    In the add-on info the addon_id is called 'slug'.

    The caller of the function should handle HassioAPIError.
    """
    hassio = hass.data[DOMAIN]
    result = await hassio.get_addon_info(addon_id)
    return result["data"]


@callback
@bind_hass
def get_homeassistant_version(hass):
    """Return latest available Home Assistant version.

    Async friendly.
    """
    if DATA_INFO not in hass.data:
        return None
    return hass.data[DATA_INFO].get("homeassistant")


@callback
@bind_hass
def get_info(hass):
    """Return generic information from Supervisor.

    Async friendly.
    """
    return hass.data.get(DATA_INFO)


@callback
@bind_hass
def get_host_info(hass):
    """Return generic host information.

    Async friendly.
    """
    return hass.data.get(DATA_HOST_INFO)


@callback
@bind_hass
def is_hassio(hass):
    """Return true if Hass.io is loaded.

    Async friendly.
    """
    return DOMAIN in hass.config.components


@callback
def get_supervisor_ip():
    """Return the supervisor ip address."""
    if "SUPERVISOR" not in os.environ:
        return None
    return os.environ["SUPERVISOR"].partition(":")[0]


async def async_setup(hass, config):
    """Set up the Hass.io component."""
    # Check local setup
    for env in ("HASSIO", "HASSIO_TOKEN"):
        if os.environ.get(env):
            continue
        _LOGGER.error("Missing %s environment variable", env)
        return False

    host = os.environ["HASSIO"]
    websession = hass.helpers.aiohttp_client.async_get_clientsession()
    hass.data[DOMAIN] = hassio = HassIO(hass.loop, websession, host)

    if not await hassio.is_connected():
        _LOGGER.warning("Not connected with Hass.io / system too busy!")

    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()

    if data is None:
        data = {}

    refresh_token = None
    if "hassio_user" in data:
        user = await hass.auth.async_get_user(data["hassio_user"])
        if user and user.refresh_tokens:
            refresh_token = list(user.refresh_tokens.values())[0]

            # Migrate old Hass.io users to be admin.
            if not user.is_admin:
                await hass.auth.async_update_user(user, group_ids=[GROUP_ID_ADMIN])

    if refresh_token is None:
        user = await hass.auth.async_create_system_user("Hass.io", [GROUP_ID_ADMIN])
        refresh_token = await hass.auth.async_create_refresh_token(user)
        data["hassio_user"] = user.id
        await store.async_save(data)

    # This overrides the normal API call that would be forwarded
    development_repo = config.get(DOMAIN, {}).get(CONF_FRONTEND_REPO)
    if development_repo is not None:
        hass.http.register_static_path(
            "/api/hassio/app", os.path.join(development_repo, "hassio/build"), False
        )

    hass.http.register_view(HassIOView(host, websession))

    await hass.components.panel_custom.async_register_panel(
        frontend_url_path="hassio",
        webcomponent_name="hassio-main",
        sidebar_title="Supervisor",
        sidebar_icon="hass:home-assistant",
        js_url="/api/hassio/app/entrypoint.js",
        embed_iframe=True,
        require_admin=True,
    )

    await hassio.update_hass_api(config.get("http", {}), refresh_token)

    last_timezone = None

    async def push_config(_):
        """Push core config to Hass.io."""
        nonlocal last_timezone

        new_timezone = str(hass.config.time_zone)

        if new_timezone == last_timezone:
            return

        last_timezone = new_timezone
        await hassio.update_hass_timezone(new_timezone)

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, push_config)

    await push_config(None)

    async def async_service_handler(service):
        """Handle service calls for Hass.io."""
        api_command = MAP_SERVICE_API[service.service][0]
        data = service.data.copy()
        addon = data.pop(ATTR_ADDON, None)
        snapshot = data.pop(ATTR_SNAPSHOT, None)
        payload = None

        # Pass data to Hass.io API
        if service.service == SERVICE_ADDON_STDIN:
            payload = data[ATTR_INPUT]
        elif MAP_SERVICE_API[service.service][3]:
            payload = data

        # Call API
        try:
            await hassio.send_command(
                api_command.format(addon=addon, snapshot=snapshot),
                payload=payload,
                timeout=MAP_SERVICE_API[service.service][2],
            )
        except HassioAPIError as err:
            _LOGGER.error("Error on Hass.io API: %s", err)

    for service, settings in MAP_SERVICE_API.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=settings[1]
        )

    async def update_info_data(now):
        """Update last available supervisor information."""
        try:
            hass.data[DATA_INFO] = await hassio.get_info()
            hass.data[DATA_HOST_INFO] = await hassio.get_host_info()
        except HassioAPIError as err:
            _LOGGER.warning("Can't read last version: %s", err)

        hass.helpers.event.async_track_point_in_utc_time(
            update_info_data, utcnow() + HASSIO_UPDATE_INTERVAL
        )

    # Fetch last version
    await update_info_data(None)

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
                "Config error. See [the logs](/config/logs) for details.",
                "Config validating",
                f"{HASS_DOMAIN}.check_config",
            )
            return

        if call.service == SERVICE_HOMEASSISTANT_RESTART:
            await hassio.restart_homeassistant()

    # Mock core services
    for service in (
        SERVICE_HOMEASSISTANT_STOP,
        SERVICE_HOMEASSISTANT_RESTART,
        SERVICE_CHECK_CONFIG,
    ):
        hass.services.async_register(HASS_DOMAIN, service, async_handle_core_service)

    # Init discovery Hass.io feature
    async_setup_discovery_view(hass, hassio)

    # Init auth Hass.io feature
    async_setup_auth_view(hass, user)

    # Init ingress Hass.io feature
    async_setup_ingress_view(hass, host)

    # Init add-on ingress panels
    await async_setup_addon_panel(hass, hassio)

    return True
