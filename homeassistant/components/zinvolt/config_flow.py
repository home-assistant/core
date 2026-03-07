"""Config flow for the Zinvolt integration."""

from __future__ import annotations

import logging
from typing import Any

import jwt
import voluptuous as vol
from zinvolt import ZinvoltClient
from zinvolt.exceptions import ZinvoltAuthenticationError, ZinvoltError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZinvoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zinvolt."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = ZinvoltClient(session=session)
            try:
                token = await client.login(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except ZinvoltAuthenticationError:
                errors["base"] = "invalid_auth"
            except ZinvoltError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Extract the user ID from the JWT token's 'sub' field
                decoded_token = jwt.decode(token, options={"verify_signature": False})
                user_id = decoded_token["sub"]
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data={CONF_ACCESS_TOKEN: token}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
