"""Services for the Blink integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_FILE_PATH,
    CONF_FILENAME,
    CONF_NAME,
    CONF_PIN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr

from .const import (
    DOMAIN,
    SERVICE_REFRESH,
    SERVICE_SAVE_RECENT_CLIPS,
    SERVICE_SAVE_VIDEO,
    SERVICE_SEND_PIN,
)
from .coordinator import BlinkUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SAVE_VIDEO_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.ensure_list,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FILENAME): cv.string,
    }
)
SERVICE_SEND_PIN_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): cv.ensure_list, vol.Optional(CONF_PIN): cv.string}
)
SERVICE_SAVE_RECENT_CLIPS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.ensure_list,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FILE_PATH): cv.string,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Blink integration."""

    async def collect_coordinators(
        device_ids: list[str],
    ) -> list[BlinkUpdateCoordinator]:
        config_entries = list[ConfigEntry]()
        registry = dr.async_get(hass)
        for target in device_ids:
            device = registry.async_get(target)
            if device:
                device_entries = list[ConfigEntry]()
                for entry_id in device.config_entries:
                    entry = hass.config_entries.async_get_entry(entry_id)
                    if entry and entry.domain == DOMAIN:
                        device_entries.append(entry)
                if not device_entries:
                    raise HomeAssistantError(
                        f"Device '{target}' is not a {DOMAIN} device"
                    )
                config_entries.extend(device_entries)
            else:
                raise HomeAssistantError(
                    f"Device '{target}' not found in device registry"
                )
        coordinators = list[BlinkUpdateCoordinator]()
        for config_entry in config_entries:
            if config_entry.state != ConfigEntryState.LOADED:
                raise HomeAssistantError(f"{config_entry.title} is not loaded")
            coordinators.append(hass.data[DOMAIN][config_entry.entry_id])
        return coordinators

    async def async_handle_save_video_service(call: ServiceCall) -> None:
        """Handle save video service calls."""
        camera_name = call.data[CONF_NAME]
        video_path = call.data[CONF_FILENAME]
        if not hass.config.is_allowed_path(video_path):
            _LOGGER.error("Can't write %s, no access to path!", video_path)
            return
        for coordinator in await collect_coordinators(call.data[ATTR_DEVICE_ID]):
            all_cameras = coordinator.api.cameras
            if camera_name in all_cameras:
                try:
                    await all_cameras[camera_name].video_to_file(video_path)
                except OSError as err:
                    _LOGGER.error("Can't write image to file: %s", err)

    async def async_handle_save_recent_clips_service(call: ServiceCall) -> None:
        """Save multiple recent clips to output directory."""
        camera_name = call.data[CONF_NAME]
        clips_dir = call.data[CONF_FILE_PATH]
        if not hass.config.is_allowed_path(clips_dir):
            _LOGGER.error("Can't write to directory %s, no access to path!", clips_dir)
            return
        for coordinator in await collect_coordinators(call.data[ATTR_DEVICE_ID]):
            all_cameras = coordinator.api.cameras
            if camera_name in all_cameras:
                try:
                    await all_cameras[camera_name].save_recent_clips(
                        output_dir=clips_dir
                    )
                except OSError as err:
                    _LOGGER.error("Can't write recent clips to directory: %s", err)

    async def send_pin(call: ServiceCall):
        """Call blink to send new pin."""
        for coordinator in await collect_coordinators(call.data[ATTR_DEVICE_ID]):
            await coordinator.api.auth.send_auth_key(
                coordinator.api,
                call.data[CONF_PIN],
            )

    async def blink_refresh(call: ServiceCall):
        """Call blink to refresh info."""
        for coordinator in await collect_coordinators(call.data[ATTR_DEVICE_ID]):
            await coordinator.api.refresh(force_cache=True)

    # Register all the above services
    service_mapping = [
        (blink_refresh, SERVICE_REFRESH, None),
        (
            async_handle_save_video_service,
            SERVICE_SAVE_VIDEO,
            SERVICE_SAVE_VIDEO_SCHEMA,
        ),
        (
            async_handle_save_recent_clips_service,
            SERVICE_SAVE_RECENT_CLIPS,
            SERVICE_SAVE_RECENT_CLIPS_SCHEMA,
        ),
        (send_pin, SERVICE_SEND_PIN, SERVICE_SEND_PIN_SCHEMA),
    ]

    for service_handler, service_name, schema in service_mapping:
        hass.services.async_register(
            DOMAIN,
            service_name,
            service_handler,
            schema=schema,
        )
