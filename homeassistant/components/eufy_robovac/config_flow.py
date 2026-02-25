"""Config flow for Eufy RoboVac."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_LOCAL_KEY,
    CONF_PROTOCOL_VERSION,
    DEFAULT_PROTOCOL_VERSION,
    DOMAIN,
)
from .local_api import EufyRoboVacLocalApi, EufyRoboVacLocalApiError
from .model_mappings import MODEL_MAPPINGS

_LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL = "T2253"
SUPPORTED_PROTOCOL_VERSIONS = ("3.3", "3.4", "3.5")


def _user_step_data_schema(user_input: dict[str, str] | None = None) -> vol.Schema:
    """Return the schema for the user step."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=user_input.get(CONF_NAME, "Eufy RoboVac"),
            ): str,
            vol.Required(
                CONF_MODEL,
                default=user_input.get(CONF_MODEL, DEFAULT_MODEL),
            ): vol.In(sorted(MODEL_MAPPINGS)),
            vol.Required(
                CONF_HOST,
                default=user_input.get(CONF_HOST, ""),
            ): str,
            vol.Required(
                CONF_ID,
                default=user_input.get(CONF_ID, ""),
            ): str,
            vol.Required(
                CONF_LOCAL_KEY,
                default=user_input.get(CONF_LOCAL_KEY, ""),
            ): str,
            vol.Optional(
                CONF_PROTOCOL_VERSION,
                default=user_input.get(CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION),
            ): vol.In(SUPPORTED_PROTOCOL_VERSIONS),
        }
    )


USER_STEP_DATA_SCHEMA = _user_step_data_schema()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


async def _async_validate_input(
    hass: HomeAssistant, user_input: dict[str, str]
) -> None:
    """Validate the user input allows us to connect."""
    api = EufyRoboVacLocalApi(
        host=user_input[CONF_HOST],
        device_id=user_input[CONF_ID],
        local_key=user_input[CONF_LOCAL_KEY],
        protocol_version=user_input.get(CONF_PROTOCOL_VERSION, DEFAULT_PROTOCOL_VERSION),
    )
    try:
        dps = await api.async_get_dps(hass)
    except EufyRoboVacLocalApiError as err:
        raise CannotConnect from err

    if not dps:
        raise CannotConnect


class EufyRoboVacConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eufy RoboVac."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=USER_STEP_DATA_SCHEMA
            )

        errors: dict[str, str] = {}
        user_input = {
            **user_input,
            CONF_NAME: user_input[CONF_NAME].strip(),
            CONF_HOST: user_input[CONF_HOST].strip(),
            CONF_ID: user_input[CONF_ID].strip(),
            CONF_LOCAL_KEY: user_input[CONF_LOCAL_KEY].strip(),
        }

        try:
            await _async_validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception validating Eufy RoboVac config")
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=_user_step_data_schema(user_input),
                errors=errors,
            )

        unique_id = user_input[CONF_ID]
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data=user_input,
        )
