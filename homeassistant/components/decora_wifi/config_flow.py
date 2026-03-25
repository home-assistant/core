"""Config flow for Leviton Decora Wi-Fi integration."""

from __future__ import annotations

import contextlib
from typing import Any

from decora_wifi import DecoraWiFiSession
from decora_wifi.models.person import Person
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _try_login(email: str, password: str) -> str | None:
    """Attempt to log in, return the user ID, or None on auth failure."""
    session = DecoraWiFiSession()
    if session.login(email, password) is None:
        return None
    user_id = str(session.user._id)  # noqa: SLF001
    with contextlib.suppress(ValueError):
        Person.logout(session)
    return user_id


class DecoraWifiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Leviton Decora Wi-Fi config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                user_id = await self.hass.async_add_executor_job(
                    _try_login,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except ValueError:
                errors["base"] = "cannot_connect"
            else:
                if user_id is None:
                    errors["base"] = "invalid_auth"
                else:
                    await self.async_set_unique_id(user_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=user_input[CONF_USERNAME],
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        self._async_abort_entries_match({CONF_USERNAME: import_data[CONF_USERNAME]})

        try:
            user_id = await self.hass.async_add_executor_job(
                _try_login,
                import_data[CONF_USERNAME],
                import_data[CONF_PASSWORD],
            )
        except ValueError:
            return self.async_abort(reason="cannot_connect")

        if user_id is None:
            return self.async_abort(reason="invalid_auth")

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=import_data[CONF_USERNAME],
            data=import_data,
        )
