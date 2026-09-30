"""Services for the Alarm control panel integration."""

from typing import Final

import probatio

from homeassistant.const import (
    ATTR_CODE,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema

from .const import DATA_COMPONENT, AlarmControlPanelEntityFeature

ALARM_SERVICE_SCHEMA: Final = make_entity_service_schema(
    {probatio.Optional(ATTR_CODE): cv.string}
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the alarm control panel services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_ALARM_DISARM,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_disarm",
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_HOME,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_home",
        [AlarmControlPanelEntityFeature.ARM_HOME],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_AWAY,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_away",
        [AlarmControlPanelEntityFeature.ARM_AWAY],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_NIGHT,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_night",
        [AlarmControlPanelEntityFeature.ARM_NIGHT],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_VACATION,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_vacation",
        [AlarmControlPanelEntityFeature.ARM_VACATION],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_custom_bypass",
        [AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_TRIGGER,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_trigger",
        [AlarmControlPanelEntityFeature.TRIGGER],
    )
