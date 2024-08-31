"""Config flow for TrestSolarController integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

from trest_identity import TrestIdentityService
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class TrestSolarControllerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TrestSolarController."""

    async def async_step_user(
        self,
        user_input: Optional[dict[str, Any]] = None,  # noqa: UP007
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            identity = TrestIdentityService(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )

            info = {"title": "Trest Solar Controller"}
            try:
                await identity.authenticate_async()

                if not identity.check_token_is_expired():
                    raise InvalidAuth
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

            # Ensure this only happens if user_input is not None
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
