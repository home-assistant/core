"""Config flow for zcs_azzurro integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from zcs_azzurro_api import DeviceOfflineError, HttpRequestError, Inverter

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from . import CannotConnect, InvalidAuth
from .const import DOMAIN, SCHEMA_CLIENT_KEY, SCHEMA_FRIENDLY_NAME, SCHEMA_THINGS_KEY

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(SCHEMA_CLIENT_KEY, msg="client"): str,
        vol.Required(
            SCHEMA_THINGS_KEY, description="Thing serial", msg="thing serial"
        ): str,
        vol.Optional(
            SCHEMA_FRIENDLY_NAME,
            description="Friendly name",
            msg="friendly name",
            default="",
        ): str,
    }
)


class ZcsAzzurroHub:
    """global class."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: str,
        things_serials: str,
        friendly_name: str | None = None,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.client = client
        self.things_serials = things_serials
        self.friendly_name = friendly_name
        self.zcs_api = Inverter(
            self.client, self.things_serials, name=self.friendly_name
        )

    async def authenticate(self) -> Inverter | None:
        """Test if we can authenticate with the host."""
        _LOGGER.debug("authentication tentative for user %s", self.zcs_api.client)
        try:
            conn = await self.hass.async_add_executor_job(self.zcs_api.check_connection)
            if conn:
                return self.zcs_api
        except HttpRequestError as excp:
            _LOGGER.debug("test call failed with code %s", excp.status_code)
            if excp.status_code == 401:
                raise ConfigEntryAuthFailed from excp
            if excp.status_code == 404:
                raise CannotConnect from excp
            if excp.status_code == 403:
                raise InvalidAuth from excp
            raise CannotConnect from excp
        except DeviceOfflineError as excp:
            raise ConfigEntryNotReady from excp
        return None


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""
    _LOGGER.debug("validating input")
    hub = ZcsAzzurroHub(
        hass,
        data[SCHEMA_CLIENT_KEY],
        data[SCHEMA_THINGS_KEY],
        data[SCHEMA_FRIENDLY_NAME],
    )
    zcs_api = await hub.authenticate()

    if not zcs_api:
        _LOGGER.debug("auth_result was %s", zcs_api)
        raise InvalidAuth

    return {"title": zcs_api.name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for zcs_azzurro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        placeholders = {
            SCHEMA_CLIENT_KEY: "Client",
            SCHEMA_THINGS_KEY: "Thing serial",
            SCHEMA_FRIENDLY_NAME: "Friendly name",
        }

        errors: dict[str, str] = {}
        if user_input is not None:
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
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    description_placeholders=placeholders,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders=placeholders,
        )
