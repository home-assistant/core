"""Config flow for Lupusec integration."""

from json import JSONDecodeError
import logging
from typing import Any

import lupupy
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
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

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import the yaml config."""
        self._async_abort_entries_match(
            {
                CONF_HOST: user_input[CONF_IP_ADDRESS],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
        )
        host = user_input[CONF_IP_ADDRESS]
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        try:
            await test_host_connection(self.hass, host, username, password)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except JSONDecodeError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=user_input.get(CONF_NAME, host),
            data={
                CONF_HOST: host,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
            },
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
