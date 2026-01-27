"""Config flow for Sequence integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from GetSequenceIoApiClient import (
    SequenceApiClient,
    SequenceApiError,
    SequenceAuthError,
    SequenceConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_NAME, default="Sequence"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    client = SequenceApiClient(session, data[CONF_ACCESS_TOKEN])

    # Test the connection
    await client.async_get_accounts()

    return {"title": data[CONF_NAME]}


class SequenceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sequence."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check for duplicate names
            self._async_abort_entries_match({CONF_NAME: user_input[CONF_NAME]})

            try:
                info = await validate_input(self.hass, user_input)
            except SequenceAuthError:
                errors["base"] = "invalid_auth"
            except SequenceConnectionError:
                errors["base"] = "cannot_connect"
            except SequenceApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirm step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except SequenceAuthError:
                errors["base"] = "invalid_auth"
            except SequenceConnectionError:
                errors["base"] = "cannot_connect"
            except SequenceApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                reauth_entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
            description_placeholders={"account": self._get_reauth_entry().title},
        )
