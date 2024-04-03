"""Config flow for the Vallox integration."""

from __future__ import annotations

import logging
from typing import Any

from vallox_websocket_api import Vallox, ValloxApiException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.network import is_ip_address

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def validate_host(hass: HomeAssistant, host: str) -> None:
    """Validate that the user input allows us to connect."""

    if not is_ip_address(host):
        raise InvalidHost(f"Invalid IP address: {host}")

    client = Vallox(host)
    await client.fetch_metric_data()


class ValloxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Vallox integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors = {}

        host = user_input[CONF_HOST]

        self._async_abort_entries_match({CONF_HOST: host})

        try:
            await validate_host(self.hass, host)
        except InvalidHost:
            errors[CONF_HOST] = "invalid_host"
        except ValloxApiException:
            errors[CONF_HOST] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors[CONF_HOST] = "unknown"
        else:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    **user_input,
                    CONF_NAME: DEFAULT_NAME,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class InvalidHost(HomeAssistantError):
    """Error to indicate an invalid host was input."""
