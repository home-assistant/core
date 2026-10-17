"""Component to allow for providing device or service updates."""

from datetime import timedelta
import logging
from typing import Any, Final

import probatio

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_AUTO_UPDATE,
    ATTR_BACKUP,
    ATTR_DISPLAY_PRECISION,
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    ATTR_SKIPPED_VERSION,
    ATTR_TITLE,
    ATTR_UPDATE_PERCENTAGE,
    ATTR_VERSION,
    DATA_COMPONENT,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    SERVICE_INSTALL,
    SERVICE_SKIP,
    UpdateDeviceClass,
    UpdateEntityFeature,
    UpdateEntityStateAttribute,
)
from .entity import UpdateEntity, UpdateEntityDescription
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(minutes=15)


__all__ = [
    "ATTR_AUTO_UPDATE",
    "ATTR_BACKUP",
    "ATTR_DISPLAY_PRECISION",
    "ATTR_INSTALLED_VERSION",
    "ATTR_IN_PROGRESS",
    "ATTR_LATEST_VERSION",
    "ATTR_RELEASE_SUMMARY",
    "ATTR_RELEASE_URL",
    "ATTR_SKIPPED_VERSION",
    "ATTR_TITLE",
    "ATTR_UPDATE_PERCENTAGE",
    "ATTR_VERSION",
    "DEVICE_CLASSES_SCHEMA",
    "DOMAIN",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_INSTALL",
    "SERVICE_SKIP",
    "UpdateDeviceClass",
    "UpdateEntity",
    "UpdateEntityDescription",
    "UpdateEntityFeature",
    "UpdateEntityStateAttribute",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Select entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[UpdateEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async_setup_services(hass)

    websocket_api.async_register_command(hass, websocket_release_notes)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "update/release_notes",
        probatio.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_release_notes(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the full release notes for a entity."""
    entity = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])

    if entity is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Entity not found"
        )
        return

    if UpdateEntityFeature.RELEASE_NOTES not in entity.supported_features:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_SUPPORTED,
            "Entity does not support release notes",
        )
        return
    if entity.available is False:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_HOME_ASSISTANT_ERROR,
            "Entity is not available",
        )
        return
    connection.send_result(
        msg["id"],
        await entity.async_release_notes(),
    )
