"""Config flow for the Hypontech Cloud integration."""

from __future__ import annotations

import logging
from typing import Any

from hyponcloud import AuthenticationError, HyponCloud
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HypontechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hypontech Cloud."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                hypon = HyponCloud(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session
                )
                await hypon.connect()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (TimeoutError, ConnectionError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Use username as unique_id to prevent duplicate config entries
                await self.async_set_unique_id(
                    user_input[CONF_USERNAME].strip().lower()
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
