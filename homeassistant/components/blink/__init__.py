"""Support for Blink Home Camera System."""
import logging

from blinkpy import blinkpy
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


async def async_setup(hass, config):
    """Set up a config entry."""
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
    if DOMAIN not in hass.data:
        username = entry.data[CONF_USERNAME]
        password = entry.data[CONF_PASSWORD]
        scan_interval = entry.data[CONF_SCAN_INTERVAL]
        blink = blinkpy.Blink(
            username=username,
            password=password,
            motion_interval=DEFAULT_OFFSET,
            legacy_subdomain=False,
            no_prompt=True,
            device_id="Home Assistant",
        )
        blink.refresh_rate = scan_interval
        await hass.async_add_executor_job(blink.start)
        hass.data[DOMAIN] = {entry.unique_id: blink}

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    def force_refresh():
        """Force a blink refresh."""
        return hass.data[DOMAIN][entry.unique_id].refresh(force_cache=True)

    async def async_trigger_camera(call):
        """Trigger a camera."""
        cameras = hass.data[DOMAIN][entry.unique_id].cameras
        name = call.data[CONF_NAME]
        if name in cameras:
            await hass.async_add_executor_job(cameras[name].snap_picture)
        await hass.async_add_executor_job(force_refresh)

    async def async_blink_refresh(event_time):
        """Call blink to refresh info."""
        await hass.async_add_executor_job(force_refresh)

    async def async_save_video(call):
        """Call save video service handler."""
        await async_handle_save_video_service(hass, entry, call)

    async def async_send_pin(call):
        """Call blink to send new pin."""
        pin = call.data[CONF_PIN]
        await hass.async_add_executor_job(
            hass.data[DOMAIN][entry.unique_id].login_handler.send_auth_key,
            hass.data[DOMAIN][entry.unique_id],
            pin,
        )

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, async_blink_refresh)
    hass.services.async_register(
        DOMAIN, SERVICE_TRIGGER, async_trigger_camera, schema=SERVICE_TRIGGER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SAVE_VIDEO, async_save_video, schema=SERVICE_SAVE_VIDEO_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_PIN, async_send_pin, schema=SERVICE_SEND_PIN_SCHEMA
    )

    await hass.async_add_executor_job(force_refresh)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload Blink entry."""
    hass.data.pop(DOMAIN)

    for platform in PLATFORMS:
        hass.config_entries.async_forward_entry_unload(config_entry, platform)

    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    hass.services.async_remove(DOMAIN, SERVICE_TRIGGER)
    hass.services.async_remove(DOMAIN, SERVICE_SAVE_VIDEO_SCHEMA)

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
        all_cameras = hass.data[DOMAIN][entry.unique_id].cameras
        if camera_name in all_cameras:
            all_cameras[camera_name].video_to_file(video_path)

    try:
        await hass.async_add_executor_job(_write_video, camera_name, video_path)
    except OSError as err:
        _LOGGER.error("Can't write image to file: %s", err)
