"""Config flow for Skybell integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aioskybell import Skybell, exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import CONF_MACS, DOMAIN


@dataclass
class ValidatedInput(tuple):
    """Class for input validation from api."""

    user_id: str | None = None
    macs: list[str | None] | None = None
    error: str | None = None


class SkybellFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Skybell."""

    async def async_step_import(self, user_input: ConfigType) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].lower()
            password = user_input[CONF_PASSWORD]

            self._async_abort_entries_match({CONF_EMAIL: email})
            result = await self._async_validate_input(email, password)
            if result.error is None:
                await self.async_set_unique_id(result.user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_MACS: result.macs,
                    },
                )
            errors["base"] = result.error

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=user_input.get(CONF_EMAIL)): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def _async_validate_input(self, email: str, password: str) -> ValidatedInput:
        """Validate login credentials."""
        skybell = Skybell(
            username=email,
            password=password,
            disable_cache=True,
            session=async_get_clientsession(self.hass),
        )
        try:
            devs = await skybell.async_initialize()
            for device in devs:
                await device.async_update()
        except exceptions.SkybellAuthenticationException:
            return ValidatedInput(error="invalid_auth")
        except exceptions.SkybellException:
            return ValidatedInput(error="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            return ValidatedInput(error="unknown")
        return ValidatedInput(user_id=skybell.user_id, macs=[dev.mac for dev in devs])
