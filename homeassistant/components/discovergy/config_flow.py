"""Config flow for Discovergy integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import pydiscovergy
from pydiscovergy.authentication import BasicAuth
import pydiscovergy.error as discovergyError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def make_schema(email: str = "", password: str = "") -> vol.Schema:
    """Create schema for config flow."""
    return vol.Schema(
        {
            vol.Required(
                CONF_EMAIL,
                default=email,
            ): str,
            vol.Required(
                CONF_PASSWORD,
                default=password,
            ): str,
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discovergy."""

    VERSION = 1

    existing_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=make_schema(),
            )

        return await self._validate_and_save(user_input)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle the initial step."""
        self.existing_entry = await self.async_set_unique_id(self.context["unique_id"])

        if entry_data is None:
            return self.async_show_form(
                step_id="reauth",
                data_schema=make_schema(
                    self.existing_entry.data[CONF_EMAIL] or "",
                    self.existing_entry.data[CONF_PASSWORD] or "",
                ),
            )

        return await self._validate_and_save(entry_data, step_id="reauth")

    async def _validate_and_save(
        self, user_input: Mapping[str, Any] | None = None, step_id: str = "user"
    ) -> FlowResult:
        """Validate user input and create config entry."""
        errors = {}

        if user_input:
            try:
                await pydiscovergy.Discovergy(
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                    httpx_client=get_async_client(self.hass),
                    authentication=BasicAuth(),
                ).meters()
            except discovergyError.HTTPError:
                errors["base"] = "cannot_connect"
            except discovergyError.InvalidLogin:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error occurred while getting meters")
                errors["base"] = "unknown"
            else:
                if self.existing_entry:
                    self.hass.config_entries.async_update_entry(
                        self.existing_entry,
                        data={
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )
                    await self.hass.config_entries.async_reload(
                        self.existing_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

                # set unique id to title which is the account email
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=make_schema(),
            errors=errors,
        )
