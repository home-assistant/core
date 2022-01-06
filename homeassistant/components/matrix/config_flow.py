"""Config flow for the Matrix integration."""
from __future__ import annotations

import json
import os
from typing import Any, Final

from matrix_client.client import MatrixClient
from matrix_client.errors import MatrixHttpLibError, MatrixRequestError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_BASE,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from . import MatrixAuthentication
from .const import CONF_COMMANDS, CONF_HOMESERVER, CONF_ROOMS, DOMAIN, SESSION_FILE

CONFIG_FLOW_ADDITIONAL_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_HOMESERVER): cv.url,
        vol.Required(CONF_USERNAME): cv.matches_regex("@[^:]*:.*"),
    },
    extra=vol.ALLOW_EXTRA,
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the user input allows us to log in.

    :return: A dict containing the title and the access token corresponding to the settings provided by the input data.
    :raises vol.Invalid: if the format check fails
    :raises vol.MultipleInvalid: if multiple format checks fail
    :raises MatrixHttpLibError: if the connection fails
    :raises MatrixRequestError: if login fails
    """

    # Check the format
    CONFIG_FLOW_ADDITIONAL_SCHEMA(data)

    auth: MatrixAuthentication = MatrixAuthentication(
        config_file=os.path.join(hass.config.path(), SESSION_FILE),
        homeserver=data[CONF_HOMESERVER],
        verify_ssl=data[CONF_VERIFY_SSL],
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
    )

    # Check if we can log in
    client: MatrixClient = await hass.async_add_executor_job(auth.login)

    # If no exception is thrown during logging in
    token: str | None = ""
    if hasattr(client, "token"):
        # A new token will be assigned on first login
        token = client.token
    else:
        # Use the token from the previous login if there is no token from the client
        token = auth.auth_token(data[CONF_USERNAME])

    return {
        "title": data[CONF_USERNAME],
        CONF_ACCESS_TOKEN: token,
    }


class ConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Matrix."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}

        if user_input is None:
            user_input = {}
        else:
            try:
                info: dict[str, str] = await validate_input(self.hass, user_input)

            except MatrixHttpLibError:
                # Network error
                errors[CONF_BASE] = "cannot_connect"

            except MatrixRequestError as ex:
                # Error code definitions: https://spec.matrix.org/latest/client-server-api/#standard-error-response
                try:
                    error_code: Final[str] = json.loads(ex.content).get("errcode")

                except ValueError:
                    # The error content is not a valid JSON string.
                    errors[CONF_BASE] = "unknown"

                else:
                    if error_code in ("M_FORBIDDEN", "M_UNAUTHORIZED"):
                        errors[CONF_PASSWORD] = "invalid_auth"
                    elif error_code in ("M_INVALID_USERNAME", "M_USER_DEACTIVATED"):
                        errors[CONF_USERNAME] = "invalid_auth"
                    elif error_code in ("M_UNKNOWN_TOKEN", "M_MISSING_TOKEN"):
                        errors[CONF_BASE] = "invalid_access_token"
                    else:
                        errors[CONF_BASE] = "unknown"

            else:
                # Use access token as unique id as it can't be duplicated
                await self.async_set_unique_id(info[CONF_ACCESS_TOKEN])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOMESERVER,
                        default=user_input.get(CONF_HOMESERVER)
                        or "https://matrix-client.matrix.org",
                    ): str,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Optional(
                        CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL) or True
                    ): bool,
                }
            ),
            errors=errors,
        )
