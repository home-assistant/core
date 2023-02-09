"""Config flow for zcs_azzurro integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from . import CannotConnect, InvalidAuth
from .const import DOMAIN, SCHEMA_CLIENT_KEY, SCHEMA_THINGS_KEY
from .zcs_azzurro_api import HTTPError, ZcsAzzurroApi

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(SCHEMA_CLIENT_KEY, msg="client"): str,
        vol.Required(
            SCHEMA_THINGS_KEY, description="Thing serial", msg="thing serial"
        ): str,
    }
)


class ZcsAzzurroHub:
    """global class."""

    def __init__(self, hass: HomeAssistant, client: str, things_serials: str) -> None:
        """Initialize."""
        self.hass = hass
        self.client = client
        self.things_serials = things_serials
        self.zcs_api = ZcsAzzurroApi(self.client, self.things_serials)

    async def authenticate(self, client) -> bool:
        """Test if we can authenticate with the host."""
        _LOGGER.debug("authentication tentative for user %s", client)
        try:
            await self.hass.async_add_executor_job(
                self.zcs_api.realtime_data_request, []
            )
        except HTTPError:
            _LOGGER.debug("test call had invalid auth")
            return False
        except ConnectionError as exc:
            _LOGGER.debug("test call had connection error")
            raise CannotConnect from exc
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""
    _LOGGER.debug("validating input")
    hub = ZcsAzzurroHub(hass, data[SCHEMA_CLIENT_KEY], data[SCHEMA_THINGS_KEY])
    auth_result = await hub.authenticate(data[SCHEMA_CLIENT_KEY])

    if not auth_result:
        _LOGGER.debug("auth_result was %s", auth_result)
        raise InvalidAuth
    return {"title": data[SCHEMA_THINGS_KEY]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcs_azzurro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        placeholders = {SCHEMA_CLIENT_KEY: "Client", SCHEMA_THINGS_KEY: "Thing serial"}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug(
                "before create entity info is %s and data is %s", info, user_input
            )
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )
