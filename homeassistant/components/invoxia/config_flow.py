"""Config flow for Invoxia (unofficial) integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
import gps_tracker
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER
from .helpers import get_invoxia_client

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    cfg = gps_tracker.Config(
        password=data[CONF_PASSWORD],
        username=data[CONF_USERNAME],
    )

    async with get_invoxia_client(hass, cfg) as client:
        try:
            await client.get_devices()
        except gps_tracker.client.exceptions.UnauthorizedQuery as err:
            raise InvalidAuth from err
        except (
            gps_tracker.client.exceptions.HttpException,
            aiohttp.ClientResponseError,
        ) as err:
            raise CannotConnect from err


class InvoxiaFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Invoxia (unofficial) integration."""

    VERSION = 1

    entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_USERNAME], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication of Invoxia (unofficial)."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication."""
        if user_input is None or not self.entry:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self.hass.config_entries.async_update_entry(
                self.entry,
                data=user_input,
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
