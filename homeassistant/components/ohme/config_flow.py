"""UI configuration flow."""

from typing import Any

from ohme import OhmeApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN

USER_SCHEMA = vol.Schema({vol.Required("email"): str, vol.Required("password"): str})


class OhmeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First config step."""

        errors: dict[str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input["email"])
            self._abort_if_unique_id_configured()
            instance = OhmeApiClient(user_input["email"], user_input["password"])
            if await instance.async_refresh_session() is None:
                errors["base"] = "auth_error"
            else:
                return self.async_create_entry(
                    title=user_input["email"], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )
