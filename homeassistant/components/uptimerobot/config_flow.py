"""Config flow for Uptime Robot integration."""
from __future__ import annotations

from pyuptimerobot import UptimeRobot, UptimeRobotAccount, UptimeRobotException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import API_ATTR_OK, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


async def validate_input(hass: HomeAssistant, data: ConfigType) -> UptimeRobotAccount:
    """Validate the user input allows us to connect."""
    uptime_robot_api = UptimeRobot(data[CONF_API_KEY], async_get_clientsession(hass))

    try:
        response = await uptime_robot_api.async_get_account_details()
    except UptimeRobotException as exception:
        raise CannotConnect(exception)
    else:
        if response.status == API_ATTR_OK:
            return response.data
        raise CannotConnect(response.error.message)


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
            account = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=account.email, data=user_input)

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

        imported_config = {CONF_API_KEY: import_config[CONF_API_KEY]}

        account = await validate_input(self.hass, imported_config)
        return self.async_create_entry(title=account.email, data=imported_config)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
