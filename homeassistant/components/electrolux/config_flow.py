"""Config flow for Electrolux integration."""

from collections.abc import Mapping
import logging
from typing import Any

from electrolux_group_developer_sdk.auth.invalid_credentials_exception import (
    InvalidCredentialsException,
)
from electrolux_group_developer_sdk.auth.token_manager import TokenManager
from electrolux_group_developer_sdk.client.appliance_client import ApplianceClient
from electrolux_group_developer_sdk.client.failed_connection_exception import (
    FailedConnectionException,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from homeassistant.data_entry_flow import AbortFlow

from .const import CONF_REFRESH_TOKEN, DOMAIN, USER_AGENT

_LOGGER: logging.Logger = logging.getLogger(__name__)


class ElectroluxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Electrolux integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""

        errors = {}

        if user_input is not None:
            token_manager: TokenManager
            try:
                token_manager = await self._authenticate_user(user_input)
            except AbortFlow:
                raise
            except InvalidCredentialsException as _:
                errors["base"] = "invalid_auth"
            except FailedConnectionException as _:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.exception("Storing credentials failed", exc_info=e)
                errors["base"] = "unknown"

            # Don't allow the same device or service to be able to be set up twice
            await self.async_set_unique_id(token_manager.get_user_id())
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="Electrolux", data=user_input)

        return self._get_form(step_id="user", errors=errors)

    async def _authenticate_user(self, user_input: Mapping[str, Any]) -> TokenManager:
        token_manager = TokenManager(
            access_token=user_input[CONF_ACCESS_TOKEN],
            refresh_token=user_input[CONF_REFRESH_TOKEN],
            api_key=user_input[CONF_API_KEY],
        )

        token_manager.ensure_credentials()

        appliance_client = ApplianceClient(
            token_manager=token_manager, external_user_agent=USER_AGENT
        )

        # Test a connection in the config flow
        await appliance_client.test_connection()

        return token_manager

    def _get_form(self, step_id: str, errors: dict[str, str]) -> ConfigFlowResult:
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_ACCESS_TOKEN): str,
                    vol.Required(CONF_REFRESH_TOKEN): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "portal_link": "https://developer.electrolux.one/generateToken"
            },
        )
