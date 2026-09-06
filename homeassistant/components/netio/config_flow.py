"""Config flow for the Netio integration."""

import logging
from typing import Any, override

from Netio.exceptions import AuthError, CommunicationError
import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import create_device

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SSL, default=False): bool,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


class NetioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Netio."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                device = await self.hass.async_add_executor_job(
                    create_device, user_input
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except CommunicationError, requests.RequestException:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device.SerialNumber)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device.DeviceName or user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
