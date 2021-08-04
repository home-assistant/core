"""Config flow for Uptime Robot integration."""
from __future__ import annotations

from pyuptimerobot import UptimeRobot
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from .const import API_ATTR_OK, API_ATTR_STAT, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


async def validate_input(hass: HomeAssistant, data: ConfigType) -> None:
    """Validate the user input allows us to connect."""

    uptime_robot_api = UptimeRobot()

    monitors = await hass.async_add_executor_job(
        uptime_robot_api.getMonitors, data[CONF_API_KEY]
    )

    if not monitors or monitors.get(API_ATTR_STAT) != API_ATTR_OK:
        raise CannotConnect("Error communicating with Uptime Robot API")


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Uptime Robot."""

    VERSION = 1

    async def async_step_user(self, user_input: ConfigType | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        try:
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_KEY] == import_config[CONF_API_KEY]:
                LOGGER.warning(
                    "Already configured. This YAML configuration has already been imported. Please remove it"
                )
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title="", data={CONF_API_KEY: import_config[CONF_API_KEY]}
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
