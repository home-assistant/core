"""Config flow for the Homevolt integration."""

from __future__ import annotations

import logging
from typing import Any

from homevolt import Homevolt, HomevoltAuthenticationError, HomevoltConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


class HomevoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homevolt."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            password = user_input.get(CONF_PASSWORD)
            websession = async_get_clientsession(self.hass)
            client = Homevolt(host, password, websession=websession)
            try:
                await client.update_info()
                device = client.get_device()
                device_id = device.device_id
            except HomevoltAuthenticationError:
                errors["base"] = "invalid_auth"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Error occurred while connecting to the Homevolt battery"
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Homevolt Local",
                    data={
                        CONF_HOST: host,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
