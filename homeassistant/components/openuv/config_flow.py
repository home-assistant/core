"""Config flow to configure the OpenUV component."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, override

import probatio
from pyopenuv.client import Client
from pyopenuv.errors import OpenUvError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DEFAULT_FROM_WINDOW,
    DEFAULT_TO_WINDOW,
    DOMAIN,
)
from .coordinator import OpenUvConfigEntry

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
        probatio.Required(CONF_LOCATION): LocationSelector(
            LocationSelectorConfig(radius=False)
        ),
        probatio.Required(CONF_ELEVATION): probatio.Coerce(float),
    }
)
STEP_REAUTH_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
    }
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            CONF_FROM_WINDOW, description={"suggested_value": DEFAULT_FROM_WINDOW}
        ): probatio.Coerce(float),
        probatio.Optional(
            CONF_TO_WINDOW, description={"suggested_value": DEFAULT_TO_WINDOW}
        ): probatio.Coerce(float),
    }
)

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


@dataclass
class OpenUvData:
    """Define structured OpenUV data needed to create/re-auth an entry."""

    api_key: str
    latitude: float
    longitude: float
    elevation: float

    @property
    def unique_id(self) -> str:
        """Return the unique for this data."""
        return f"{self.latitude}, {self.longitude}"


class OpenUvFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an OpenUV config flow."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize."""
        self._reauth_data: Mapping[str, Any] = {}

    async def _async_verify(
        self, data: OpenUvData, error_step_id: str, error_schema: probatio.Schema
    ) -> ConfigFlowResult:
        """Verify the credentials and create/re-auth the entry."""
        websession = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(data.api_key, 0, 0, session=websession)

        try:
            await client.uv_index()
        except OpenUvError:
            return self.async_show_form(
                step_id=error_step_id,
                data_schema=error_schema,
                errors={CONF_API_KEY: "invalid_api_key"},
                description_placeholders={
                    CONF_LATITUDE: str(data.latitude),
                    CONF_LONGITUDE: str(data.longitude),
                },
            )

        entry_data = {
            CONF_API_KEY: data.api_key,
            CONF_LOCATION: {
                CONF_LATITUDE: data.latitude,
                CONF_LONGITUDE: data.longitude,
            },
            CONF_ELEVATION: data.elevation,
        }

        if existing_entry := await self.async_set_unique_id(data.unique_id):
            self.hass.config_entries.async_update_entry(existing_entry, data=entry_data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")
        return self.async_create_entry(title=data.unique_id, data=entry_data)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: OpenUvConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Define the config flow to handle options."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._reauth_data = entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_SCHEMA,
                description_placeholders={**self._reauth_data[CONF_LOCATION]},
            )

        data = OpenUvData(
            user_input[CONF_API_KEY],
            self._reauth_data[CONF_LOCATION][CONF_LATITUDE],
            self._reauth_data[CONF_LOCATION][CONF_LONGITUDE],
            self._reauth_data[CONF_ELEVATION],
        )

        return await self._async_verify(data, "reauth_confirm", STEP_REAUTH_SCHEMA)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_SCHEMA,
                    {
                        CONF_LOCATION: {
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                        CONF_ELEVATION: self.hass.config.elevation,
                    },
                ),
            )

        data = OpenUvData(
            user_input[CONF_API_KEY],
            user_input[CONF_LOCATION][CONF_LATITUDE],
            user_input[CONF_LOCATION][CONF_LONGITUDE],
            user_input[CONF_ELEVATION],
        )

        await self.async_set_unique_id(data.unique_id)
        self._abort_if_unique_id_configured()

        return await self._async_verify(
            data,
            "user",
            self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
        )
