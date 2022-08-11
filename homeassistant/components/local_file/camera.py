"""Camera that loads a picture from a local file."""
from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any

import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.components.repairs.issue_handler import async_create_issue
from homeassistant.components.repairs.models import IssueSeverity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_FILE_PATH, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN, SERVICE_UPDATE_FILE_PATH

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILE_PATH): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Camera that works with local files."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2022.11.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Local File camera."""
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LocalFile(data, entry.entry_id)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_UPDATE_FILE_PATH,
        {
            vol.Required(ATTR_ENTITY_ID): cv.comp_entity_ids,
            vol.Required(CONF_FILE_PATH): cv.string,
        },
        "async_update_file_path_service",
    )


class LocalFile(Camera):
    """Representation of a local file camera."""

    _attr_has_entity_name = True

    def __init__(self, data: dict[str, Any], entry_id: str) -> None:
        """Initialize Local File Camera component."""
        super().__init__()

        self._file_path = data[CONF_FILE_PATH]
        # Set content type of local file
        content, _ = mimetypes.guess_type(self._file_path)
        if content is not None:
            self.content_type = content
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)}, name=data[CONF_NAME]
        )

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return image response."""
        try:
            with open(self._file_path, "rb") as file:
                return file.read()
        except FileNotFoundError:
            _LOGGER.warning(
                "Could not read camera %s image from file: %s",
                self.entity_id,
                self._file_path,
            )
        return None

    async def async_update_file_path_service(self, file_path: str) -> None:
        """Update the file_path."""
        if not os.access(file_path, os.R_OK):
            _LOGGER.error(
                "Could not read camera %s image from file: %s",
                self.entity_id,
                file_path,
            )
            return
        self._file_path = file_path
        content, _ = mimetypes.guess_type(file_path)
        if content is not None:
            self.content_type = content
        self.async_schedule_update_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the camera state attributes."""
        return {CONF_FILE_PATH: self._file_path}
