"""Config flow for the SensorPush Cloud integration."""

from __future__ import annotations

from typing import Any

from sensorpush_ha import SensorPushCloudApi, SensorPushCloudAuthError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER


class SensorPushCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SensorPush Cloud."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email, password = user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()
            clientsession = async_get_clientsession(self.hass)
            api = SensorPushCloudApi(email, password, clientsession)
            try:
                await api.async_authorize()
            except SensorPushCloudAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=email, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.EMAIL, autocomplete="username"
                        )
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                }
            ),
            errors=errors,
        )
