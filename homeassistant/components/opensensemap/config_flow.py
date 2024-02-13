"""Config flow for OpenSenseMap."""
from typing import Any

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_STATION_ID, DOMAIN


class OpenSenseMapConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for OpenSky."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._station_id: str | None = None
        self._name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None, error: str | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        if user_input is not None:
            self._station_id = user_input[CONF_STATION_ID]
            self._name = user_input.get(CONF_NAME)
            return await self._async_check_and_create_on_success(
                return_form_on_error=True
            )

        errors = {}
        if error is not None:
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_ID): cv.string,
                    vol.Optional(CONF_NAME): cv.string,
                }
            ),
        )

    async def _async_check_and_create_on_success(
        self, return_form_on_error: bool
    ) -> FlowResult:
        """Try to fetch station info and return CREATE_ENTRY result on success."""
        station_api = OpenSenseMap(self._station_id, async_get_clientsession(self.hass))
        try:
            await station_api.get_data()

        except OpenSenseMapError:
            return self.async_abort(reason="can_not_connect")

        if (received_name := station_api.data.get("name", None)) is None:
            if return_form_on_error:
                return await self.async_step_user(user_input=None, error="invalid_id")
            return self.async_abort(reason="invalid_id")

        await self.async_set_unique_id(self._station_id)
        self._abort_if_unique_id_configured()

        name = self._name or received_name
        config_data = {
            CONF_STATION_ID: self._station_id,
            CONF_NAME: name,
        }
        return self.async_create_entry(title=name, data=config_data)

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import config from yaml."""
        self._station_id = import_config.get(CONF_STATION_ID)
        self._name = import_config.get(CONF_NAME, None)

        return await self._async_check_and_create_on_success(return_form_on_error=False)
