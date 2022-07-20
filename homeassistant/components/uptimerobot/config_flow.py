"""Config flow for UptimeRobot integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pyuptimerobot import (
    UptimeRobot,
    UptimeRobotAccount,
    UptimeRobotApiError,
    UptimeRobotApiResponse,
    UptimeRobotAuthenticationException,
    UptimeRobotException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_ATTR_OK, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UptimeRobot."""

    VERSION = 1

    async def _validate_input(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], UptimeRobotAccount | None]:
        """Validate the user input allows us to connect."""
        errors: dict[str, str] = {}
        response: UptimeRobotApiResponse | UptimeRobotApiError | None = None
        key: str = data[CONF_API_KEY]
        if key.startswith("ur") or key.startswith("m"):
            LOGGER.error("Wrong API key type detected, use the 'main' API key")
            errors["base"] = "not_main_key"
            return errors, None
        uptime_robot_api = UptimeRobot(key, async_get_clientsession(self.hass))

        try:
            response = await uptime_robot_api.async_get_account_details()
        except UptimeRobotAuthenticationException as exception:
            LOGGER.error(exception)
            errors["base"] = "invalid_api_key"
        except UptimeRobotException as exception:
            LOGGER.error(exception)
            errors["base"] = "cannot_connect"
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.exception(exception)
            errors["base"] = "unknown"
        else:
            if response.status != API_ATTR_OK:
                errors["base"] = "unknown"
                LOGGER.error(response.error.message)

        account: UptimeRobotAccount | None = (
            response.data
            if response and response.data and response.data.email
            else None
        )

        return errors, account

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors, account = await self._validate_input(user_input)
        if account:
            await self.async_set_unique_id(str(account.user_id))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=account.email, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Return the reauth confirm step."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA
            )
        errors, account = await self._validate_input(user_input)
        if account:
            if self.context.get("unique_id") and self.context["unique_id"] != str(
                account.user_id
            ):
                errors["base"] = "reauth_failed_matching_account"
            else:
                existing_entry = await self.async_set_unique_id(str(account.user_id))
                if existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                return self.async_abort(reason="reauth_failed_existing")

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
