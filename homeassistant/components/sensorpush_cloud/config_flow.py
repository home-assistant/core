"""Config flow for the SensorPush Cloud integration."""

from __future__ import annotations

from typing import Any

from sensorpush_ha import SensorPushCloudApi, SensorPushCloudError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN, LOGGER


class SensorPushCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SensorPush Cloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email, password = user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            await self.async_set_unique_id(email, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            try:
                api = SensorPushCloudApi(self.hass, email, password)
                await api.async_authorize()
            except SensorPushCloudError as e:
                errors["base"] = str(e)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=email, data=user_input)

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
