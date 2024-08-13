"""Config flow for Lupusec integration."""

from json import JSONDecodeError
import logging
from typing import Any

import lupupy
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class LupusecConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Lupusec config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            host = user_input[CONF_HOST]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                await test_host_connection(self.hass, host, username, password)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except JSONDecodeError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            else:
                return self.async_create_entry(
                    title=host,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


async def test_host_connection(
    hass: HomeAssistant, host: str, username: str, password: str
):
    """Test if the host is reachable and is actually a Lupusec device."""

    try:
        await hass.async_add_executor_job(lupupy.Lupusec, username, password, host)
    except lupupy.LupusecException as ex:
        _LOGGER.error("Failed to connect to Lupusec device at %s", host)
        raise CannotConnect from ex


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
