"""Services for the HEOS integration."""

import logging

from pyheos import CommandFailedError, Heos, HeosError, const
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_PASSWORD,
    ATTR_USERNAME,
    DOMAIN,
    SERVICE_SIGN_IN,
    SERVICE_SIGN_OUT,
)

_LOGGER = logging.getLogger(__name__)

HEOS_SIGN_IN_SCHEMA = vol.Schema(
    {vol.Required(ATTR_USERNAME): cv.string, vol.Required(ATTR_PASSWORD): cv.string}
)

HEOS_SIGN_OUT_SCHEMA = vol.Schema({})


def register(hass: HomeAssistant):
    """Register HEOS services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SIGN_IN,
        _sign_in_handler,
        schema=HEOS_SIGN_IN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SIGN_OUT,
        _sign_out_handler,
        schema=HEOS_SIGN_OUT_SCHEMA,
    )


def _get_controller(hass: HomeAssistant) -> Heos:
    """Get the HEOS controller instance."""
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, DOMAIN)
    if not entry or not entry.state == ConfigEntryState.LOADED:
        raise HomeAssistantError("The HEOS integration is not loaded")
    return entry.runtime_data.controller_manager.controller


async def _sign_in_handler(service: ServiceCall) -> None:
    """Sign in to the HEOS account."""

    _LOGGER.warning(
        "The action 'heos.sign_in' is deprecated and will be removed in the 2025.4 release; "
        "set the credentials in the configuration options and the integration will sign in automatically"
    )

    controller = _get_controller(service.hass)
    if controller.connection_state != const.STATE_CONNECTED:
        _LOGGER.error("Unable to sign in because HEOS is not connected")
        return
    username = service.data[ATTR_USERNAME]
    password = service.data[ATTR_PASSWORD]
    try:
        await controller.sign_in(username, password)
    except CommandFailedError as err:
        _LOGGER.error("Sign in failed: %s", err)
    except HeosError as err:
        _LOGGER.error("Unable to sign in: %s", err)


async def _sign_out_handler(service: ServiceCall) -> None:
    """Sign out of the HEOS account."""

    _LOGGER.warning(
        "The action 'heos.sign_out' is deprecated and will be removed in the 2025.4 release"
    )

    controller = _get_controller(service.hass)
    if controller.connection_state != const.STATE_CONNECTED:
        _LOGGER.error("Unable to sign out because HEOS is not connected")
        return
    try:
        await controller.sign_out()
    except HeosError as err:
        _LOGGER.error("Unable to sign out: %s", err)
