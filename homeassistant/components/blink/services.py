"""Services for the Blink integration."""
from __future__ import annotations

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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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

SERVICE_SAVE_VIDEO_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FILENAME): cv.string,
    }
)
SERVICE_SEND_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_PIN): cv.string,
    }
)
SERVICE_SAVE_RECENT_CLIPS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FILE_PATH): cv.string,
    }
)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Blink integration."""

    def collect_coordinators(
        device_ids: list[str],
    ) -> list[BlinkUpdateCoordinator]:
        config_entries: list[ConfigEntry] = []
        registry = dr.async_get(hass)
        for target in device_ids:
            device = registry.async_get(target)
            if device:
                device_entries: list[ConfigEntry] = []
                for entry_id in device.config_entries:
                    entry = hass.config_entries.async_get_entry(entry_id)
                    if entry and entry.domain == DOMAIN:
                        device_entries.append(entry)
                if not device_entries:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="invalid_device",
                        translation_placeholders={"target": target, "domain": DOMAIN},
                    )
                config_entries.extend(device_entries)
            else:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="device_not_found",
                    translation_placeholders={"target": target},
                )

        coordinators: list[BlinkUpdateCoordinator] = []
        for config_entry in config_entries:
            if config_entry.state != ConfigEntryState.LOADED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_loaded",
                    translation_placeholders={"target": config_entry.title},
                )

            coordinators.append(hass.data[DOMAIN][config_entry.entry_id])
        return coordinators

    async def async_handle_save_video_service(call: ServiceCall) -> None:
        """Handle save video service calls."""
        camera_name = call.data[CONF_NAME]
        video_path = call.data[CONF_FILENAME]
        if not hass.config.is_allowed_path(video_path):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_path",
                translation_placeholders={"target": video_path},
            )

        for coordinator in collect_coordinators(call.data[ATTR_DEVICE_ID]):
            all_cameras = coordinator.api.cameras
            if camera_name in all_cameras:
                try:
                    await all_cameras[camera_name].video_to_file(video_path)
                except OSError as err:
                    raise ServiceValidationError(
                        str(err),
                        translation_domain=DOMAIN,
                        translation_key="cant_write",
                    ) from err

    async def async_handle_save_recent_clips_service(call: ServiceCall) -> None:
        """Save multiple recent clips to output directory."""
        camera_name = call.data[CONF_NAME]
        clips_dir = call.data[CONF_FILE_PATH]
        if not hass.config.is_allowed_path(clips_dir):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_path",
                translation_placeholders={"target": clips_dir},
            )

        for coordinator in collect_coordinators(call.data[ATTR_DEVICE_ID]):
            all_cameras = coordinator.api.cameras
            if camera_name in all_cameras:
                try:
                    await all_cameras[camera_name].save_recent_clips(
                        output_dir=clips_dir
                    )
                except OSError as err:
                    raise ServiceValidationError(
                        str(err),
                        translation_domain=DOMAIN,
                        translation_key="cant_write",
                    ) from err

    async def send_pin(call: ServiceCall):
        """Call blink to send new pin."""
        for coordinator in collect_coordinators(call.data[ATTR_DEVICE_ID]):
            await coordinator.api.auth.send_auth_key(
                coordinator.api,
                call.data[CONF_PIN],
            )

    async def blink_refresh(call: ServiceCall):
        """Call blink to refresh info."""
        for coordinator in collect_coordinators(call.data[ATTR_DEVICE_ID]):
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
