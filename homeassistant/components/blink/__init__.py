"""Support for Blink Home Camera System."""
import asyncio
import logging

from blinkpy.blinkpy import Blink
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_FILENAME,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_OFFSET,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_ID,
    DOMAIN,
    PLATFORMS,
    SERVICE_REFRESH,
    SERVICE_SAVE_VIDEO,
    SERVICE_SEND_PIN,
    SERVICE_TRIGGER,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_TRIGGER_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})
SERVICE_SAVE_VIDEO_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Required(CONF_FILENAME): cv.string}
)
SERVICE_SEND_PIN_SCHEMA = vol.Schema({vol.Optional(CONF_PIN): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _blink_startup_wrapper(entry):
    """Startup wrapper for blink."""
    blink = Blink(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        motion_interval=DEFAULT_OFFSET,
        legacy_subdomain=False,
        no_prompt=True,
        device_id=DEVICE_ID,
    )
    blink.refresh_rate = entry.data[CONF_SCAN_INTERVAL]

    try:
        blink.login_response = entry.data["login_response"]
        blink.setup_params(entry.data["login_response"])
    except KeyError:
        blink.get_auth_token()

    blink.setup_params(entry.data["login_response"])
    blink.setup_post_verify()
    return blink


async def async_setup(hass, config):
    """Set up a config entry."""
    hass.data[DOMAIN] = {}
    if DOMAIN not in config:
        return True

    conf = config.get(DOMAIN, {})

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up Blink via config entry."""
    hass.data[DOMAIN][entry.entry_id] = await hass.async_add_executor_job(
        _blink_startup_wrapper, entry
    )

    if not hass.data[DOMAIN][entry.entry_id].available:
        _LOGGER.error("Blink unavailable for setup")
        return False

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    def trigger_camera(call):
        """Trigger a camera."""
        cameras = hass.data[DOMAIN][entry.entry_id].cameras
        name = call.data[CONF_NAME]
        if name in cameras:
            cameras[name].snap_picture()
        blink_refresh()

    def blink_refresh(event_time=None):
        """Call blink to refresh info."""
        hass.data[DOMAIN][entry.entry_id].refresh(force_cache=True)

    async def async_save_video(call):
        """Call save video service handler."""
        await async_handle_save_video_service(hass, entry, call)

    def send_pin(call):
        """Call blink to send new pin."""
        pin = call.data[CONF_PIN]
        hass.data[DOMAIN][entry.entry_id].login_handler.send_auth_key(
            hass.data[DOMAIN][entry.entry_id], pin,
        )

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, blink_refresh)
    hass.services.async_register(
        DOMAIN, SERVICE_TRIGGER, trigger_camera, schema=SERVICE_TRIGGER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_VIDEO, async_save_video, schema=SERVICE_SAVE_VIDEO_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_PIN, send_pin, schema=SERVICE_SEND_PIN_SCHEMA
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload Blink entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if not unload_ok:
        return False

    hass.data[DOMAIN].pop(entry.entry_id)

    if len(hass.data[DOMAIN]) != 0:
        return True

    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    hass.services.async_remove(DOMAIN, SERVICE_TRIGGER)
    hass.services.async_remove(DOMAIN, SERVICE_SAVE_VIDEO_SCHEMA)
    hass.services.async_remove(DOMAIN, SERVICE_SEND_PIN)

    return True


async def async_handle_save_video_service(hass, entry, call):
    """Handle save video service calls."""
    camera_name = call.data[CONF_NAME]
    video_path = call.data[CONF_FILENAME]
    if not hass.config.is_allowed_path(video_path):
        _LOGGER.error("Can't write %s, no access to path!", video_path)
        return

    def _write_video(camera_name, video_path):
        """Call video write."""
        all_cameras = hass.data[DOMAIN][entry.entry_id].cameras
        if camera_name in all_cameras:
            all_cameras[camera_name].video_to_file(video_path)

    try:
        await hass.async_add_executor_job(_write_video, camera_name, video_path)
    except OSError as err:
        _LOGGER.error("Can't write image to file: %s", err)
