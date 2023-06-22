"""Support for Blink Home Camera System."""
import asyncio
from copy import deepcopy
import logging

from aiohttp import ClientError
from blinkpy.auth import Auth
from blinkpy.blinkpy import Blink
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import (
    CONF_FILE_PATH,
    CONF_FILENAME,
    CONF_NAME,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_REFRESH,
    SERVICE_SAVE_RECENT_CLIPS,
    SERVICE_SAVE_VIDEO,
    SERVICE_SEND_PIN,
)
from .coordinator import BlinkUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SAVE_VIDEO_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Required(CONF_FILENAME): cv.string}
)
SERVICE_SEND_PIN_SCHEMA = vol.Schema({vol.Optional(CONF_PIN): cv.string})
SERVICE_SAVE_RECENT_CLIPS_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Required(CONF_FILE_PATH): cv.string}
)


def _reauth_flow_wrapper(hass, data):
    """Reauth flow wrapper."""
    hass.add_job(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_REAUTH}, data=data
        )
    )
    persistent_notification.async_create(
        hass,
        (
            "Blink configuration migrated to a new version. Please go to the"
            " integrations page to re-configure (such as sending a new 2FA key)."
        ),
        "Blink Migration",
    )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle migration of a previous version config entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)
    data = {**entry.data}
    if entry.version == 1:
        data.pop("login_response", None)
        await hass.async_add_executor_job(_reauth_flow_wrapper, hass, data)
        return False
    if entry.version == 2:
        await hass.async_add_executor_job(_reauth_flow_wrapper, hass, data)
        return False
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Blink via config entry."""
    hass.data.setdefault(DOMAIN, {})

    _async_import_options_from_data_if_missing(hass, entry)
    blink = Blink(session=async_get_clientsession(hass))
    auth_data = deepcopy(dict(entry.data))
    blink.auth = Auth(auth_data, no_prompt=True, session=async_get_clientsession(hass))
    blink.refresh_rate = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = BlinkUpdateCoordinator(hass, blink)

    try:
        await coordinator.api.start()
        if coordinator.api.auth.check_key_required():
            _LOGGER.debug("Attempting a reauth flow")
            _reauth_flow_wrapper(hass, auth_data)
    except (ClientError, asyncio.TimeoutError) as ex:
        raise ConfigEntryNotReady("Can not connect to host") from ex

    hass.data[DOMAIN][entry.entry_id] = coordinator

    if not blink.available:
        raise ConfigEntryNotReady

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    await coordinator.async_config_entry_first_refresh()

    async def blink_refresh(event_time=None):
        """Call blink to refresh info."""
        await hass.data[DOMAIN][entry.entry_id].api.refresh(force_cache=True)

    async def async_save_video(call):
        """Call save video service handler."""
        await async_handle_save_video_service(hass, entry, call)

    async def async_save_recent_clips(call):
        """Call save recent clips service handler."""
        await async_handle_save_recent_clips_service(hass, entry, call)

    async def send_pin(call):
        """Call blink to send new pin."""
        pin = call.data[CONF_PIN]
        await hass.data[DOMAIN][entry.entry_id].api.auth.send_auth_key(
            hass.data[DOMAIN][entry.entry_id].api,
            pin,
        )

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, blink_refresh)
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_VIDEO, async_save_video, schema=SERVICE_SAVE_VIDEO_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_RECENT_CLIPS,
        async_save_recent_clips,
        schema=SERVICE_SAVE_RECENT_CLIPS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_PIN, send_pin, schema=SERVICE_SEND_PIN_SCHEMA
    )

    return True


@callback
def _async_import_options_from_data_if_missing(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    options = dict(entry.options)
    if CONF_SCAN_INTERVAL not in entry.options:
        options[CONF_SCAN_INTERVAL] = entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        hass.config_entries.async_update_entry(entry, options=options)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Blink entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if not unload_ok:
        return False

    hass.data[DOMAIN].pop(entry.entry_id)

    if len(hass.data[DOMAIN]) != 0:
        return True

    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    hass.services.async_remove(DOMAIN, SERVICE_SAVE_VIDEO)
    hass.services.async_remove(DOMAIN, SERVICE_SEND_PIN)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    blink: Blink = hass.data[DOMAIN][entry.entry_id].api
    blink.refresh_rate = entry.options[CONF_SCAN_INTERVAL]


async def async_handle_save_video_service(
    hass: HomeAssistant, entry: ConfigEntry, call
) -> None:
    """Handle save video service calls."""
    camera_name = call.data[CONF_NAME]
    video_path = call.data[CONF_FILENAME]
    if not hass.config.is_allowed_path(video_path):
        _LOGGER.error("Can't write %s, no access to path!", video_path)
        return
    try:
        all_cameras = hass.data[DOMAIN][entry.entry_id].api.cameras
        if camera_name in all_cameras:
            await all_cameras[camera_name].video_to_file(video_path)

    except OSError as err:
        _LOGGER.error("Can't write image to file: %s", err)


async def async_handle_save_recent_clips_service(
    hass: HomeAssistant, entry: ConfigEntry, call
) -> None:
    """Save multiple recent clips to output directory."""
    camera_name = call.data[CONF_NAME]
    clips_dir = call.data[CONF_FILE_PATH]
    if not hass.config.is_allowed_path(clips_dir):
        _LOGGER.error("Can't write to directory %s, no access to path!", clips_dir)
        return

    try:
        all_cameras = hass.data[DOMAIN][entry.entry_id].api.cameras
        if camera_name in all_cameras:
            await all_cameras[camera_name].save_recent_clips(output_dir=clips_dir)
    except OSError as err:
        _LOGGER.error("Can't write recent clips to directory: %s", err)
