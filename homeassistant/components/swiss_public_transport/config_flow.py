"""Config flow for swiss_public_transport."""
import logging
from typing import Any

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import (
    OpendataTransportConnectionError,
    OpendataTransportError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_DESTINATION,
    CONF_RATE,
    CONF_START,
    DEFAULT_RATE,
    DOMAIN,
    PLACEHOLDERS,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_START): cv.string,
        vol.Required(CONF_DESTINATION): cv.string,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_RATE, default=DEFAULT_RATE): NumberSelector(
            NumberSelectorConfig(min=0, mode=NumberSelectorMode.BOX)
        )
    },
)

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}

_LOGGER = logging.getLogger(__name__)


class SwissPublicTransportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Swiss public transport config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
            except Exception:  # pylint: disable=broad-except
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

    async def async_step_import(self, import_input: dict[str, Any]) -> FlowResult:
        """Async import step to set up the connection."""
        await self.async_set_unique_id(
            f"{import_input[CONF_START]} {import_input[CONF_DESTINATION]}"
        )
        self._abort_if_unique_id_configured()

        session = async_get_clientsession(self.hass)
        opendata = OpendataTransport(
            import_input[CONF_START], import_input[CONF_DESTINATION], session
        )
        try:
            await opendata.async_get_data()
        except OpendataTransportConnectionError:
            return self.async_abort(reason="cannot_connect")
        except OpendataTransportError:
            return self.async_abort(reason="bad_config")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error(
                "Unknown error raised by python-opendata-transport for '%s %s', check at http://transport.opendata.ch/examples/stationboard.html if your station names and your parameters are valid",
                import_input[CONF_START],
                import_input[CONF_DESTINATION],
            )
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=import_input[CONF_NAME],
            data=import_input,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
