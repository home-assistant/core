"""Support for AlarmDecoder-based alarm control panels (Honeywell/DSC)."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.const import ATTR_CODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_KEYPRESS = "keypress"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "alarm_toggle_chime",
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={
            vol.Required(ATTR_CODE): cv.string,
        },
        func="alarm_toggle_chime",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "alarm_keypress",
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={
            vol.Required(ATTR_KEYPRESS): cv.string,
        },
        func="alarm_keypress",
    )
