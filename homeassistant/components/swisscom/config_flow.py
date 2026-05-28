"""Config flow for the Swisscom Internet-Box integration."""

import logging
from typing import Any

from swisscom_internet_box import (
    SwisscomAuthError,
    SwisscomClient,
    SwisscomConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SwisscomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Swisscom Internet-Box."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = SwisscomClient(
                async_get_clientsession(self.hass),
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await client.login()
                info = await client.get_box_info()
            except SwisscomAuthError:
                errors["base"] = "invalid_auth"
            except SwisscomConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during Swisscom config flow")
                errors["base"] = "unknown"
            else:
                if info.base_mac:
                    await self.async_set_unique_id(format_mac(info.base_mac))
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.model_name or "Internet-Box", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
