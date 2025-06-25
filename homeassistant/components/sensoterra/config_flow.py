"""Config flow for Sensoterra integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from jwt import DecodeError, decode
from sensoterra.customerapi import (
    CustomerApi,
    InvalidAuth as StInvalidAuth,
    Timeout as StTimeout,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER, TOKEN_EXPIRATION_DAYS

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class SensoterraConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sensoterra."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create hub entry based on config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = CustomerApi(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            # We need a unique tag per HA instance
            uuid = self.hass.data["core.uuid"]
            expiration = datetime.now() + timedelta(TOKEN_EXPIRATION_DAYS)

            try:
                token: str = await api.get_token(
                    f"Home Assistant {uuid}", "READONLY", expiration
                )
                decoded_token = decode(
                    token, algorithms=["HS256"], options={"verify_signature": False}
                )

            except StInvalidAuth as exp:
                LOGGER.error(
                    "Login attempt with %s: %s", user_input[CONF_EMAIL], exp.message
                )
                errors["base"] = "invalid_auth"
            except StTimeout:
                LOGGER.error("Login attempt with %s: time out", user_input[CONF_EMAIL])
                errors["base"] = "cannot_connect"
            except DecodeError:
                LOGGER.error("Login attempt with %s: bad token", user_input[CONF_EMAIL])
                errors["base"] = "invalid_access_token"
            else:
                device_unique_id = decoded_token["sub"]
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_TOKEN: token,
                        CONF_EMAIL: user_input[CONF_EMAIL],
                    },
                )

        return self.async_show_form(
            step_id=SOURCE_USER,
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
