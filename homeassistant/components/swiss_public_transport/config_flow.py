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
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_DESTINATION, CONF_START, CONF_VIA, DOMAIN, MAX_VIA, PLACEHOLDERS
from .helper import unique_id_from_config

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_START): cv.string,
        vol.Optional(CONF_VIA): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Required(CONF_DESTINATION): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


class SwissPublicTransportConfigFlow(ConfigFlow, domain=DOMAIN):
    """Swiss public transport config flow."""

    VERSION = 2
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Async user step to set up the connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = unique_id_from_config(user_input)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            if CONF_VIA in user_input and len(user_input[CONF_VIA]) > MAX_VIA:
                errors["base"] = "too_many_via_stations"
            else:
                session = async_get_clientsession(self.hass)
                opendata = OpendataTransport(
                    user_input[CONF_START],
                    user_input[CONF_DESTINATION],
                    session,
                    via=user_input.get(CONF_VIA),
                )
                try:
                    await opendata.async_get_data()
                except OpendataTransportConnectionError:
                    errors["base"] = "cannot_connect"
                except OpendataTransportError:
                    errors["base"] = "bad_config"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unknown error")
                    errors["base"] = "unknown"
                else:
                    return self.async_create_entry(
                        title=unique_id,
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )
