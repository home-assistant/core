"""Config flow for Roborock."""
from __future__ import annotations

import logging
from typing import Any

from roborock.api import RoborockApiClient
from roborock.containers import UserData
from roborock.exceptions import (
    RoborockAccountDoesNotExist,
    RoborockException,
    RoborockInvalidCode,
    RoborockInvalidEmail,
    RoborockUrlException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_BASE_URL, CONF_ENTRY_CODE, CONF_USER_DATA, DOMAIN

_LOGGER = logging.getLogger(__name__)


class RoborockFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roborock."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._client: RoborockApiClient | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()
            self._username = username
            _LOGGER.debug("Requesting code for Roborock account")
            self._client = RoborockApiClient(username)
            try:
                await self._client.request_code()
            except RoborockAccountDoesNotExist:
                errors["base"] = "invalid_email"
            except RoborockUrlException:
                errors["base"] = "unknown_url"
            except RoborockInvalidEmail:
                errors["base"] = "invalid_email_format"
            except RoborockException as ex:
                _LOGGER.exception(ex)
                errors["base"] = "unknown_roborock"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception(ex)
                errors["base"] = "unknown"
            else:
                return await self.async_step_code()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_USERNAME): str}),
            errors=errors,
        )

    async def async_step_code(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        assert self._client
        assert self._username
        if user_input is not None:
            code = user_input[CONF_ENTRY_CODE]
            _LOGGER.debug("Logging into Roborock account using email provided code")
            try:
                login_data = await self._client.code_login(code)
            except RoborockInvalidCode:
                errors["base"] = "invalid_code"
            except RoborockException as ex:
                _LOGGER.exception(ex)
                errors["base"] = "unknown_roborock"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception(ex)
                errors["base"] = "unknown"
            else:
                return self._create_entry(self._client, self._username, login_data)

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema({vol.Required(CONF_ENTRY_CODE): str}),
            errors=errors,
        )

    def _create_entry(
        self, client: RoborockApiClient, username: str, user_data: UserData
    ) -> FlowResult:
        """Finished config flow and create entry."""
        return self.async_create_entry(
            title=username,
            data={
                CONF_USERNAME: username,
                CONF_USER_DATA: user_data.as_dict(),
                CONF_BASE_URL: client.base_url,
            },
        )
