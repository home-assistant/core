"""Support for ZoneMinder."""

from enum import StrEnum
import logging

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZoneMinderService(StrEnum):
    """Store keys for ZoneMinder services."""

    SET_RUN_STATE = "set_run_state"


class ZoneMinderServiceArgument(StrEnum):
    """Store keys for ZoneMinder service arguments."""

    ID = "id"
    NAME = "name"


SET_RUN_STATE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ZoneMinderServiceArgument.ID): cv.string,
        probatio.Required(ZoneMinderServiceArgument.NAME): cv.string,
    }
)


def _set_active_state(call: ServiceCall) -> None:
    """Set the ZoneMinder run state to the given state name."""
    zm_id = call.data[ZoneMinderServiceArgument.ID]
    state_name = call.data[ZoneMinderServiceArgument.NAME]
    if zm_id not in call.hass.data[DOMAIN]:
        _LOGGER.error("Invalid ZoneMinder host provided: %s", zm_id)
    if not call.hass.data[DOMAIN][zm_id].set_active_state(state_name):
        _LOGGER.error(
            "Unable to change ZoneMinder state. Host: %s, state: %s",
            zm_id,
            state_name,
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register ZoneMinder services."""

    hass.services.async_register(
        DOMAIN,
        ZoneMinderService.SET_RUN_STATE,
        _set_active_state,
        schema=SET_RUN_STATE_SCHEMA,
    )
