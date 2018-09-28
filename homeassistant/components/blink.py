"""
Support for Blink Home Camera System.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/blink/
"""
import logging
from datetime import timedelta

import asyncio
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, CONF_NAME,
    CONF_SCAN_INTERVAL, CONF_FILENAME)

REQUIREMENTS = ['blinkpy==0.9.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blink'
DEFAULT_BRAND = 'blink'
DEFAULT_ATTRIBUTION = "Data provided by immedia-semi.com"
SIGNAL_UPDATE_BLINK = "blink_update"
SCAN_INTERVAL = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_TRIGGER = 'trigger_camera'
SERVICE_SAVE_VIDEO = 'save_video'

SERVICE_TRIGGER_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})

SERVICE_SAVE_VIDEO_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_FILENAME): cv.template,
})


def setup(hass, config):
    """Set up Blink System."""
    from blinkpy import blinkpy
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    scan_interval = config[DOMAIN].get(CONF_SCAN_INTERVAL)
    hass.data[DOMAIN] = blinkpy.Blink(username=username,
                                      password=password)
    hass.data[DOMAIN].refresh_rate = scan_interval.total_seconds()
    hass.data[DOMAIN].start()

    def trigger_camera(call):
        """Trigger a camera."""
        cameras = hass.data[DOMAIN].sync.cameras
        name = call.data.get(CONF_NAME, '')
        if name in cameras:
            cameras[name].snap_picture()
        hass.data[DOMAIN].refresh(force_cache=True)

    def blink_refresh(event_time):
        """Call blink to refresh info."""
        _LOGGER.info("Updating Blink component")
        hass.data[DOMAIN].refresh(force_cache=True)

    @asyncio.coroutine
    def async_save_video(call):
        """Call save video service handler."""
        result = yield from async_handle_save_video_service(hass, call)
        if not result:
            return False
        return True

    hass.services.register(DOMAIN, 'update', blink_refresh)
    hass.services.register(DOMAIN,
                           SERVICE_TRIGGER,
                           trigger_camera,
                           schema=SERVICE_TRIGGER_SCHEMA)
    hass.services.async_register(DOMAIN,
                                 SERVICE_SAVE_VIDEO,
                                 async_save_video,
                                 schema=SERVICE_SAVE_VIDEO_SCHEMA)
    return True


async def async_handle_save_video_service(hass, call):
    """Handle save video service calls."""
    camera_name = call.data.get(CONF_NAME)
    video_path = call.data.get(CONF_FILENAME)
    if not hass.config.is_allowed_path(video_path):
        _LOGGER.error(
            "Can't write %s, no access to path!", video_path)
        return

    def _write_video(camera_name, video_path):
        """Call video write."""
        all_cameras = hass.data[DOMAIN].sync.cameras
        if camera_name in all_cameras:
            all_cameras[camera_name].video_to_file(video_path)

    try:
        await hass.async_add_executor_job(
            _write_video, camera_name, video_path)
    except OSError as err:
        _LOGGER.error("Can't write image to file: %s", err)
