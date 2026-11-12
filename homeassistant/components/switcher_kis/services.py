"""Services for the Switcher integration."""

from enum import StrEnum

import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class SwitcherService(StrEnum):
    """Store keys for Switcher services."""

    SET_AUTO_OFF = "set_auto_off"
    TURN_ON_WITH_TIMER = "turn_on_with_timer"


class SwitcherServiceArgument(StrEnum):
    """Store keys for Switcher service arguments."""

    AUTO_OFF = "auto_off"
    TIMER_MINUTES = "timer_minutes"


SERVICE_SET_AUTO_OFF_SCHEMA: VolDictType = {
    probatio.Required(SwitcherServiceArgument.AUTO_OFF): cv.time_period_str,
}
SERVICE_TURN_ON_WITH_TIMER_SCHEMA: VolDictType = {
    probatio.Required(SwitcherServiceArgument.TIMER_MINUTES): probatio.All(
        cv.positive_int, probatio.Range(min=1, max=150)
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Switcher integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SwitcherService.SET_AUTO_OFF,
        entity_domain=SWITCH_DOMAIN,
        schema=SERVICE_SET_AUTO_OFF_SCHEMA,
        func="async_set_auto_off_service",
        entity_device_classes=(SwitchDeviceClass.SWITCH,),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SwitcherService.TURN_ON_WITH_TIMER,
        entity_domain=SWITCH_DOMAIN,
        schema=SERVICE_TURN_ON_WITH_TIMER_SCHEMA,
        func="async_turn_on_with_timer_service",
        entity_device_classes=(SwitchDeviceClass.SWITCH,),
    )
