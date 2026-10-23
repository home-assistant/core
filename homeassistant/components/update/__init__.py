"""Component to allow for providing device or service updates."""

from contextlib import suppress
from datetime import timedelta
import logging
from typing import Any, Final

import probatio

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.translation import async_get_translations
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
    UpdateReleaseNotesMessageSeverity,
    UpdateService,
    UpdateServiceArgument,
)
from .entity import UpdateEntity, UpdateEntityDescription, UpdateReleaseNotesMessage
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(minutes=15)


RELEASE_NOTES_MESSAGE_BATTERY_POWERED = UpdateReleaseNotesMessage(
    translation_domain=DOMAIN,
    translation_key="battery_powered_update",
)
RELEASE_NOTES_MESSAGE_DO_NOT_INTERRUPT = UpdateReleaseNotesMessage(
    translation_domain=DOMAIN,
    translation_key="do_not_interrupt",
    severity=UpdateReleaseNotesMessageSeverity.WARNING,
)


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
    "RELEASE_NOTES_MESSAGE_BATTERY_POWERED",
    "RELEASE_NOTES_MESSAGE_DO_NOT_INTERRUPT",
    "SERVICE_INSTALL",
    "SERVICE_SKIP",
    "UpdateDeviceClass",
    "UpdateEntity",
    "UpdateEntityDescription",
    "UpdateEntityFeature",
    "UpdateEntityStateAttribute",
    "UpdateReleaseNotesMessage",
    "UpdateReleaseNotesMessageSeverity",
    "UpdateService",
    "UpdateServiceArgument",
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)


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
        await _async_render_release_notes(hass, entity),
    )


async def _async_render_release_notes(
    hass: HomeAssistant, entity: UpdateEntity
) -> str | None:
    """Render release notes messages followed by the entity release notes."""
    release_notes = await entity.async_release_notes()
    # Like the state, but a skipped version can still be installed
    if entity.latest_version == entity.installed_version or not entity.has_update:
        return release_notes
    release_notes_messages = await _async_render_release_notes_messages(
        hass, entity.release_notes_messages
    )

    if release_notes_messages is None:
        return release_notes
    if not release_notes:
        return release_notes_messages
    return f"{release_notes_messages}\n\n{release_notes}"


async def _async_render_release_notes_messages(
    hass: HomeAssistant, messages: tuple[UpdateReleaseNotesMessage, ...]
) -> str | None:
    """Render release notes messages as alert elements."""
    if not messages:
        return None

    entity_component_translations = await async_get_translations(
        hass, hass.config.language, "entity_component", {DOMAIN}
    )
    entity_translations = await async_get_translations(
        hass,
        hass.config.language,
        "entity",
        {
            message.translation_domain
            for message in messages
            if message.translation_domain != DOMAIN
        },
    )

    rendered_messages: list[str] = []
    for message in messages:
        if message.translation_domain == DOMAIN:
            translation = entity_component_translations.get(
                "component.update.entity_component.release_notes_messages."
                f"{message.translation_key}"
            )
        else:
            translation = entity_translations.get(
                f"component.{message.translation_domain}.entity.update."
                f"release_notes_messages.{message.translation_key}"
            )
        if translation is None:
            _LOGGER.warning(
                "Missing translation for release notes message %s of %s",
                message.translation_key,
                message.translation_domain,
            )
            continue
        if message.translation_placeholders is not None:
            with suppress(KeyError):
                translation = translation.format(**message.translation_placeholders)
        rendered_messages.append(
            f'<ha-alert alert-type="{message.severity}">{translation}</ha-alert>'
        )

    return "\n\n".join(rendered_messages) or None
