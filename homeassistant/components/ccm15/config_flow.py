"""Config flow for Midea ccm15 AC Controller integration."""

import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=80): cv.port,
    }
)


async def _test_connection(hass: HomeAssistant, host: str, port: int) -> bool:
    """Probe the controller's status endpoint using HA's shared httpx client."""
    client = get_async_client(hass)
    try:
        response = await client.get(
            f"http://{host}:{port}/status.xml", timeout=DEFAULT_TIMEOUT
        )
    except httpx.RequestError:
        return False
    return response.status_code == 200


class CCM15ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Midea ccm15 AC Controller."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            try:
                if not await _test_connection(
                    self.hass, user_input[CONF_HOST], user_input[CONF_PORT]
                ):
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
