"""Config flow for the UniFi Access integration."""

from __future__ import annotations

import logging
from typing import Any

from uiaccessclient import ApiClient, SpaceApi
from uiaccessclient.openapi.exceptions import ForbiddenException, UnauthorizedException
import urllib3.exceptions
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DEFAULT_HOSTNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOSTNAME): str,
        vol.Required(CONF_API_TOKEN): str,
    }
)


class UniFiAccessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UniFi Access."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Process configuration form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            await _validate_input(self.hass, user_input, errors)
            if not errors:
                return self.async_create_entry(title="UniFi Access", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


async def _validate_input(
    hass: HomeAssistant, data: dict[str, Any], errors: dict[str, str]
) -> None:
    api_client = ApiClient(data[CONF_HOST], data[CONF_API_TOKEN])
    space_api = SpaceApi(api_client)

    try:
        await hass.async_add_executor_job(space_api.fetch_all_doors)
    except (
        UnauthorizedException,
        ForbiddenException,
    ):
        errors["base"] = "invalid_auth"
    except urllib3.exceptions.HTTPError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"
