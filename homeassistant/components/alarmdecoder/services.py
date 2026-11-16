"""Support for AlarmDecoder-based alarm control panels (Honeywell/DSC)."""

from enum import StrEnum

import probatio

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class AlarmDecoderService(StrEnum):
    """Store keys for AlarmDecoder services."""

    ALARM_KEYPRESS = "alarm_keypress"
    ALARM_TOGGLE_CHIME = "alarm_toggle_chime"


class AlarmDecoderServiceArgument(StrEnum):
    """Store keys for AlarmDecoder service arguments."""

    KEYPRESS = "keypress"
    CODE = "code"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AlarmDecoderService.ALARM_TOGGLE_CHIME,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={
            probatio.Required(AlarmDecoderServiceArgument.CODE): cv.string,
        },
        func="alarm_toggle_chime",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        AlarmDecoderService.ALARM_KEYPRESS,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        schema={
            probatio.Required(AlarmDecoderServiceArgument.KEYPRESS): cv.string,
        },
        func="alarm_keypress",
    )
