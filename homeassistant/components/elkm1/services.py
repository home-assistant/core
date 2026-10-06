"""Support the ElkM1 Gold and ElkM1 EZ8 alarm/integration panels."""

from datetime import timedelta

from elkm1_lib.elk import Elk, Panel
import probatio

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import SERVICE_ALARM_ARM_VACATION
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import VolDictType
from homeassistant.util import dt as dt_util

from .const import ATTR_DURATION, ATTR_VALUE, DOMAIN, ELK_USER_CODE_SERVICE_SCHEMA
from .models import ELKM1Data

SERVICE_ALARM_ARM_HOME_INSTANT = "alarm_arm_home_instant"
SERVICE_ALARM_ARM_NIGHT_INSTANT = "alarm_arm_night_instant"
SERVICE_ALARM_BYPASS = "alarm_bypass"
SERVICE_ALARM_CLEAR_BYPASS = "alarm_clear_bypass"
SERVICE_ALARM_DISPLAY_MESSAGE = "alarm_display_message"
SERVICE_SENSOR_COUNTER_REFRESH = "sensor_counter_refresh"
SERVICE_SENSOR_COUNTER_SET = "sensor_counter_set"
SERVICE_SENSOR_ZONE_BYPASS = "sensor_zone_bypass"
SERVICE_SENSOR_ZONE_TRIGGER = "sensor_zone_trigger"
SERVICE_SWITCH_OUTPUT_TURN_ON_FOR = "switch_output_turn_on_for"

DISPLAY_MESSAGE_SERVICE_SCHEMA: VolDictType = {
    probatio.Optional("clear", default=2): probatio.All(
        probatio.Coerce(int), probatio.In([0, 1, 2])
    ),
    probatio.Optional("beep", default=False): cv.boolean,
    probatio.Optional("timeout", default=0): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=65535)
    ),
    probatio.Optional("line1", default=""): cv.string,
    probatio.Optional("line2", default=""): cv.string,
}

ELK_SET_COUNTER_SERVICE_SCHEMA: VolDictType = {
    probatio.Required(ATTR_VALUE): probatio.All(
        probatio.Coerce(int), probatio.Range(0, 65535)
    )
}

ELK_OUTPUT_TURN_ON_FOR_SERVICE_SCHEMA: VolDictType = {
    probatio.Required(ATTR_DURATION): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(seconds=1), max=timedelta(seconds=65535)),
    ),
}

SPEAK_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required("number"): probatio.All(
            probatio.Coerce(int), probatio.Range(min=0, max=999)
        ),
        probatio.Optional("prefix", default=""): cv.string,
    }
)

SET_TIME_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Optional("prefix", default=""): cv.string,
    }
)


def _find_elk_by_prefix(hass: HomeAssistant, prefix: str) -> Elk | None:
    """Search all config entries for a given prefix."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if not entry.runtime_data:
            continue
        elk_data: ELKM1Data = entry.runtime_data
        if elk_data.prefix == prefix:
            return elk_data.elk
    return None


@callback
def _async_get_elk_panel(service: ServiceCall) -> Panel:
    """Get the ElkM1 panel from a service call."""
    prefix = service.data["prefix"]
    elk = _find_elk_by_prefix(service.hass, prefix)
    if elk is None:
        raise HomeAssistantError(f"No ElkM1 with prefix '{prefix}' found")
    return elk.panel


@callback
def _speak_word_service(service: ServiceCall) -> None:
    _async_get_elk_panel(service).speak_word(service.data["number"])


@callback
def _speak_phrase_service(service: ServiceCall) -> None:
    _async_get_elk_panel(service).speak_phrase(service.data["number"])


@callback
def _set_time_service(service: ServiceCall) -> None:
    _async_get_elk_panel(service).set_time(dt_util.now())


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Create ElkM1 services."""

    hass.services.async_register(
        DOMAIN, "speak_word", _speak_word_service, SPEAK_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "speak_phrase", _speak_phrase_service, SPEAK_SERVICE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "set_time", _set_time_service, SET_TIME_SERVICE_SCHEMA
    )

    for service_name, func in (
        (SERVICE_ALARM_ARM_VACATION, "async_alarm_arm_vacation"),
        (SERVICE_ALARM_ARM_HOME_INSTANT, "async_alarm_arm_home_instant"),
        (SERVICE_ALARM_ARM_NIGHT_INSTANT, "async_alarm_arm_night_instant"),
        (SERVICE_ALARM_BYPASS, "async_bypass"),
        (SERVICE_ALARM_CLEAR_BYPASS, "async_clear_bypass"),
    ):
        async_register_platform_entity_service(
            hass,
            DOMAIN,
            service_name,
            entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
            func=func,
            schema=ELK_USER_CODE_SERVICE_SCHEMA,
        )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ALARM_DISPLAY_MESSAGE,
        entity_domain=ALARM_CONTROL_PANEL_DOMAIN,
        func="async_display_message",
        schema=DISPLAY_MESSAGE_SERVICE_SCHEMA,
    )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SENSOR_COUNTER_REFRESH,
        entity_domain=SENSOR_DOMAIN,
        func="async_counter_refresh",
        schema=None,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SENSOR_COUNTER_SET,
        entity_domain=SENSOR_DOMAIN,
        func="async_counter_set",
        schema=ELK_SET_COUNTER_SERVICE_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SENSOR_ZONE_BYPASS,
        entity_domain=SENSOR_DOMAIN,
        func="async_zone_bypass",
        schema=ELK_USER_CODE_SERVICE_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SENSOR_ZONE_TRIGGER,
        entity_domain=SENSOR_DOMAIN,
        func="async_zone_trigger",
        schema=None,
    )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SWITCH_OUTPUT_TURN_ON_FOR,
        entity_domain=SWITCH_DOMAIN,
        func="async_switch_output_turn_on_for",
        schema=ELK_OUTPUT_TURN_ON_FOR_SERVICE_SCHEMA,
    )
