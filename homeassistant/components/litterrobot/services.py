"""Litter-Robot services."""

from enum import StrEnum

import probatio

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class LitterRobotService(StrEnum):
    """Store keys for Litter-Robot services."""

    SET_SLEEP_MODE = "set_sleep_mode"


class LitterRobotServiceArgument(StrEnum):
    """Store keys for Litter-Robot service arguments."""

    ENABLED = "enabled"
    START_TIME = "start_time"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        LitterRobotService.SET_SLEEP_MODE,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Required(LitterRobotServiceArgument.ENABLED): cv.boolean,
            probatio.Optional(LitterRobotServiceArgument.START_TIME): cv.time,
        },
        func="async_set_sleep_mode",
    )
