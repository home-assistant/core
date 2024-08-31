"""Config flow to configure the OpenUV component."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pyopenuv import Client
from pyopenuv.errors import OpenUvError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DEFAULT_FROM_WINDOW,
    DEFAULT_TO_WINDOW,
    DOMAIN,
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_FROM_WINDOW, description={"suggested_value": DEFAULT_FROM_WINDOW}
        ): vol.Coerce(float),
        vol.Optional(
            CONF_TO_WINDOW, description={"suggested_value": DEFAULT_TO_WINDOW}
        ): vol.Coerce(float),
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


class OpenUvFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an OpenUV config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self._reauth_data: Mapping[str, Any] = {}

    @property
    def step_user_schema(self) -> vol.Schema:
        """Return the config schema."""
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Inclusive(
                    CONF_LATITUDE, "coords", default=self.hass.config.latitude
                ): cv.latitude,
                vol.Inclusive(
                    CONF_LONGITUDE, "coords", default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(
                    CONF_ELEVATION, default=self.hass.config.elevation
                ): vol.Coerce(float),
            }
        )

    async def _async_verify(
        self, data: OpenUvData, error_step_id: str, error_schema: vol.Schema
    ) -> FlowResult:
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
            CONF_LATITUDE: data.latitude,
            CONF_LONGITUDE: data.longitude,
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
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Define the config flow to handle options."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._reauth_data = entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_SCHEMA,
                description_placeholders={
                    CONF_LATITUDE: self._reauth_data[CONF_LATITUDE],
                    CONF_LONGITUDE: self._reauth_data[CONF_LONGITUDE],
                },
            )

        data = OpenUvData(
            user_input[CONF_API_KEY],
            self._reauth_data[CONF_LATITUDE],
            self._reauth_data[CONF_LONGITUDE],
            self._reauth_data[CONF_ELEVATION],
        )

        return await self._async_verify(data, "reauth_confirm", STEP_REAUTH_SCHEMA)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=self.step_user_schema
            )

        data = OpenUvData(
            user_input[CONF_API_KEY],
            user_input[CONF_LATITUDE],
            user_input[CONF_LONGITUDE],
            user_input[CONF_ELEVATION],
        )

        await self.async_set_unique_id(data.unique_id)
        self._abort_if_unique_id_configured()

        return await self._async_verify(data, "user", self.step_user_schema)
