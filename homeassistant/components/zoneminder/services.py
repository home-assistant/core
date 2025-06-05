"""Support for ZoneMinder."""

import logging

import voluptuous as vol

from homeassistant.const import ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_RUN_STATE = "set_run_state"
SET_RUN_STATE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ID): cv.string, vol.Required(ATTR_NAME): cv.string}
)


def _set_active_state(call: ServiceCall) -> None:
    """Set the ZoneMinder run state to the given state name."""
    zm_id = call.data[ATTR_ID]
    state_name = call.data[ATTR_NAME]
    if zm_id not in call.hass.data[DOMAIN]:
        _LOGGER.error("Invalid ZoneMinder host provided: %s", zm_id)
    if not call.hass.data[DOMAIN][zm_id].set_active_state(state_name):
        _LOGGER.error(
            "Unable to change ZoneMinder state. Host: %s, state: %s",
            zm_id,
            state_name,
        )


def register_services(hass: HomeAssistant) -> None:
    """Register ZoneMinder services."""

    hass.services.async_register(
        DOMAIN, SERVICE_SET_RUN_STATE, _set_active_state, schema=SET_RUN_STATE_SCHEMA
    )
