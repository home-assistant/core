"""Config flow for AirTouch 3 Air Conditioner integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as ConfigFlowBase, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN
from .coordinator import async_fetch_airtouch_data

_LOGGER = logging.getLogger(__name__)


def _host_schema(default_host: Any = vol.UNDEFINED) -> vol.Schema:
    """Return the host form schema."""
    return vol.Schema({vol.Required(CONF_HOST, default=default_host): str})


STEP_USER_DATA_SCHEMA = _host_schema()


async def validate_input(_hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        await async_fetch_airtouch_data(data[CONF_HOST])
    except UpdateFailed as err:
        raise CannotConnect from err

    return {"title": "AirTouch 3 Air Conditioner"}


class AirTouch3ConfigFlow(ConfigFlowBase, domain=DOMAIN):
    """Handle a config flow for AirTouch 3 Air Conditioner."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        reconfigure_entry = self._get_reconfigure_entry()
        default_host = reconfigure_entry.data[CONF_HOST]
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
            default_host = user_input[CONF_HOST]
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: user_input[CONF_HOST]},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_host_schema(default_host),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
