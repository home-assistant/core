"""Services for the Alarm control panel integration."""

from typing import Final

import probatio

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema

from .const import (
    DATA_COMPONENT,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelService,
    AlarmControlPanelServiceArgument,
)

ALARM_SERVICE_SCHEMA: Final = make_entity_service_schema(
    {probatio.Optional(AlarmControlPanelServiceArgument.CODE): cv.string}
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the alarm control panel services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        AlarmControlPanelService.DISARM,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_disarm",
    )
    component.async_register_entity_service(
        AlarmControlPanelService.ARM_HOME,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_home",
        [AlarmControlPanelEntityFeature.ARM_HOME],
    )
    component.async_register_entity_service(
        AlarmControlPanelService.ARM_AWAY,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_away",
        [AlarmControlPanelEntityFeature.ARM_AWAY],
    )
    component.async_register_entity_service(
        AlarmControlPanelService.ARM_NIGHT,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_night",
        [AlarmControlPanelEntityFeature.ARM_NIGHT],
    )
    component.async_register_entity_service(
        AlarmControlPanelService.ARM_VACATION,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_vacation",
        [AlarmControlPanelEntityFeature.ARM_VACATION],
    )
    component.async_register_entity_service(
        AlarmControlPanelService.ARM_CUSTOM_BYPASS,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_custom_bypass",
        [AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS],
    )
    component.async_register_entity_service(
        AlarmControlPanelService.TRIGGER,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_trigger",
        [AlarmControlPanelEntityFeature.TRIGGER],
    )
