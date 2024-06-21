"""Config flow for swiss_public_transport."""

import logging
from typing import Any

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_DESTINATION, CONF_START, DOMAIN, PLACEHOLDERS

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_START): cv.string,
        vol.Required(CONF_DESTINATION): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


class SwissPublicTransportConfigFlow(ConfigFlow, domain=DOMAIN):
    """Swiss public transport config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Async user step to set up the connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_START]} {user_input[CONF_DESTINATION]}"
            )
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            opendata = OpendataTransport(
                user_input[CONF_START], user_input[CONF_DESTINATION], session
            )
            try:
                await opendata.async_get_data()
            except OpendataTransportConnectionError:
                errors["base"] = "cannot_connect"
            except OpendataTransportError:
                errors["base"] = "bad_config"
            except Exception:
                _LOGGER.exception("Unknown error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{user_input[CONF_START]} {user_input[CONF_DESTINATION]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )
