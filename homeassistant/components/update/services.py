"""Services for the Update integration."""

from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_BACKUP,
    ATTR_VERSION,
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_INSTALL,
    SERVICE_SKIP,
    UpdateEntityFeature,
)

if TYPE_CHECKING:
    from . import UpdateEntity


async def _async_install(entity: UpdateEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to validate the call."""
    # If version is not specified, but no update is available.
    if (version := service_call.data.get(ATTR_VERSION)) is None and (
        entity.installed_version == entity.latest_version
        or entity.latest_version is None
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_update_available",
            translation_placeholders={"entity_id": entity.entity_id},
        )

    # If version is specified, but not supported by the entity.
    if (
        version is not None
        and UpdateEntityFeature.SPECIFIC_VERSION not in entity.supported_features
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="specific_version_not_supported",
            translation_placeholders={"entity_id": entity.entity_id},
        )

    # If backup is requested, but not supported by the entity.
    if (
        backup := service_call.data[ATTR_BACKUP]
    ) and UpdateEntityFeature.BACKUP not in entity.supported_features:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="backup_not_supported",
            translation_placeholders={"entity_id": entity.entity_id},
        )

    # Update is already in progress.
    if entity.in_progress is not False:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="update_in_progress",
            translation_placeholders={"entity_id": entity.entity_id},
        )

    await entity.async_install_with_progress(version, backup)


async def _async_skip(entity: UpdateEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to validate the call."""
    if entity.auto_update:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="skip_not_supported",
            translation_placeholders={"entity_id": entity.entity_id},
        )
    await entity.async_skip()


async def _async_clear_skipped(entity: UpdateEntity, service_call: ServiceCall) -> None:
    """Service call wrapper to validate the call."""
    if entity.auto_update:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="clear_skipped_not_supported",
            translation_placeholders={"entity_id": entity.entity_id},
        )
    await entity.async_clear_skipped()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the update services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_INSTALL,
        {
            probatio.Optional(ATTR_VERSION): cv.string,
            probatio.Optional(ATTR_BACKUP, default=False): cv.boolean,
        },
        _async_install,
        [UpdateEntityFeature.INSTALL],
        admin_only=True,
    )

    component.async_register_entity_service(
        SERVICE_SKIP,
        None,
        _async_skip,
        admin_only=True,
    )
    component.async_register_entity_service(
        "clear_skipped",
        None,
        _async_clear_skipped,
        admin_only=True,
    )
