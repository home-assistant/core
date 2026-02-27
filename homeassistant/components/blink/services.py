"""Services for the Blink integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_FILE_PATH,
    CONF_FILENAME,
    CONF_PIN,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir, service

from .const import DOMAIN

# Deprecated
SERVICE_SEND_PIN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_PIN): cv.string,
    }
)


async def _send_pin(call: ServiceCall) -> None:
    """Call blink to send new pin."""
    # Create repair issue to inform user about service removal
    ir.async_create_issue(
        call.hass,
        DOMAIN,
        "service_send_pin_deprecation",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.ERROR,
        breaks_in_ha_version="2026.5.0",
        translation_key="service_send_pin_deprecation",
        translation_placeholders={"service_name": f"{call.domain}.{call.service}"},
    )

    # Service has been removed - raise exception
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="service_removed",
        translation_placeholders={"service_name": f"{call.domain}.{call.service}"},
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Blink integration."""

    hass.services.async_register(
        DOMAIN,
        "send_pin",
        _send_pin,
        schema=SERVICE_SEND_PIN_SCHEMA,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "record",
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="record",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "trigger_camera",
        entity_domain=CAMERA_DOMAIN,
        schema=None,
        func="trigger_camera",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "save_recent_clips",
        entity_domain=CAMERA_DOMAIN,
        schema={vol.Required(CONF_FILE_PATH): cv.string},
        func="save_recent_clips",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "save_video",
        entity_domain=CAMERA_DOMAIN,
        schema={vol.Required(CONF_FILENAME): cv.string},
        func="save_video",
    )
