"""Camera that loads a picture from a local file."""

from __future__ import annotations

import logging
import mimetypes

import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA as CAMERA_PLATFORM_SCHEMA,
    Camera,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_FILE_PATH, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_platform,
    issue_registry as ir,
)
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .const import DEFAULT_NAME, DOMAIN, SERVICE_UPDATE_FILE_PATH
from .util import check_file_path_access

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = CAMERA_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILE_PATH): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Camera for local file from a config entry."""

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_UPDATE_FILE_PATH,
        {
            vol.Required(CONF_FILE_PATH): cv.string,
        },
        "update_file_path",
    )

    async_add_entities(
        [
            LocalFile(
                entry.options[CONF_NAME],
                entry.options[CONF_FILE_PATH],
                entry.entry_id,
            )
        ]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Camera that works with local files."""
    file_path: str = config[CONF_FILE_PATH]
    file_path_slug = slugify(file_path)

    if not await hass.async_add_executor_job(check_file_path_access, file_path):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"no_access_path_{file_path_slug}",
            breaks_in_ha_version="2025.5.0",
            is_fixable=False,
            learn_more_url="https://www.home-assistant.io/integrations/local_file/",
            severity=ir.IssueSeverity.WARNING,
            translation_key="no_access_path",
            translation_placeholders={
                "file_path": file_path_slug,
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        learn_more_url="https://www.home-assistant.io/integrations/local_file/",
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Local file",
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


class LocalFile(Camera):
    """Representation of a local file camera."""

    def __init__(self, name: str, file_path: str, unique_id: str) -> None:
        """Initialize Local File Camera component."""
        super().__init__()
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._file_path = file_path
        # Set content type of local file
        content, _ = mimetypes.guess_type(file_path)
        if content is not None:
            self.content_type = content

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
                self.name,
                self._file_path,
            )
        return None

    async def update_file_path(self, file_path: str) -> None:
        """Update the file_path."""
        if not await self.hass.async_add_executor_job(
            check_file_path_access, file_path
        ):
            raise ServiceValidationError(f"Path {file_path} is not accessible")
        self._file_path = file_path
        self.schedule_update_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the camera state attributes."""
        return {"file_path": self._file_path}
