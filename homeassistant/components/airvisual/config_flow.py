"""Define a config flow manager for AirVisual."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pyairvisual.cloud_api import (
    CloudAPI,
    InvalidKeyError,
    KeyExpiredError,
    NotFoundError,
    UnauthorizedError,
)
from pyairvisual.errors import AirVisualError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from . import async_get_geography_id
from .const import (
    CONF_CITY,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    INTEGRATION_TYPE_GEOGRAPHY_NAME,
    LOGGER,
)

API_KEY_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): cv.string})
GEOGRAPHY_NAME_SCHEMA = API_KEY_DATA_SCHEMA.extend(
    {
        vol.Required(CONF_CITY): cv.string,
        vol.Required(CONF_STATE): cv.string,
        vol.Required(CONF_COUNTRY): cv.string,
    }
)
PICK_INTEGRATION_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): vol.In(
            [
                INTEGRATION_TYPE_GEOGRAPHY_COORDS,
                INTEGRATION_TYPE_GEOGRAPHY_NAME,
            ]
        )
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {vol.Required(CONF_SHOW_ON_MAP): bool},
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class AirVisualFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an AirVisual config flow."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._entry_data_for_reauth: Mapping[str, Any] = {}
        self._geo_id: str | None = None

    @property
    def geography_coords_schema(self) -> vol.Schema:
        """Return the data schema for the cloud API."""
        return API_KEY_DATA_SCHEMA.extend(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )

    async def _async_finish_geography(
        self, user_input: dict[str, str], integration_type: str
    ) -> FlowResult:
        """Validate a Cloud API key."""
        errors = {}
        websession = aiohttp_client.async_get_clientsession(self.hass)
        cloud_api = CloudAPI(user_input[CONF_API_KEY], session=websession)

        # If this is the first (and only the first) time we've seen this API key, check
        # that it's valid:
        valid_keys = self.hass.data.setdefault("airvisual_checked_api_keys", set())
        valid_keys_lock = self.hass.data.setdefault(
            "airvisual_checked_api_keys_lock", asyncio.Lock()
        )

        async with valid_keys_lock:
            if user_input[CONF_API_KEY] not in valid_keys:
                if integration_type == INTEGRATION_TYPE_GEOGRAPHY_COORDS:
                    coro = cloud_api.air_quality.nearest_city()
                    error_schema = self.geography_coords_schema
                    error_step = "geography_by_coords"
                else:
                    coro = cloud_api.air_quality.city(
                        user_input[CONF_CITY],
                        user_input[CONF_STATE],
                        user_input[CONF_COUNTRY],
                    )
                    error_schema = GEOGRAPHY_NAME_SCHEMA
                    error_step = "geography_by_name"

                try:
                    await coro
                except (InvalidKeyError, KeyExpiredError, UnauthorizedError):
                    errors[CONF_API_KEY] = "invalid_api_key"
                except NotFoundError:
                    errors[CONF_CITY] = "location_not_found"
                except AirVisualError as err:
                    LOGGER.error(err)
                    errors["base"] = "unknown"

                if errors:
                    return self.async_show_form(
                        step_id=error_step, data_schema=error_schema, errors=errors
                    )

                valid_keys.add(user_input[CONF_API_KEY])

        if existing_entry := await self.async_set_unique_id(self._geo_id):
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=f"Cloud API ({self._geo_id})",
            data={**user_input, CONF_INTEGRATION_TYPE: integration_type},
        )

    async def _async_init_geography(
        self, user_input: dict[str, str], integration_type: str
    ) -> FlowResult:
        """Handle the initialization of the integration via the cloud API."""
        self._geo_id = async_get_geography_id(user_input)
        await self._async_set_unique_id(self._geo_id)
        self._abort_if_unique_id_configured()
        return await self._async_finish_geography(user_input, integration_type)

    async def _async_set_unique_id(self, unique_id: str) -> None:
        """Set the unique ID of the config flow and abort if it already exists."""
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Define the config flow to handle options."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_import(self, import_data: dict[str, str]) -> FlowResult:
        """Handle import of config entry version 1 data."""
        import_source = import_data.pop("import_source")
        if import_source == "geography_by_coords":
            return await self.async_step_geography_by_coords(import_data)
        return await self.async_step_geography_by_name(import_data)

    async def async_step_geography_by_coords(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initialization of the cloud API based on latitude/longitude."""
        if not user_input:
            return self.async_show_form(
                step_id="geography_by_coords", data_schema=self.geography_coords_schema
            )

        return await self._async_init_geography(
            user_input, INTEGRATION_TYPE_GEOGRAPHY_COORDS
        )

    async def async_step_geography_by_name(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initialization of the cloud API based on city/state/country."""
        if not user_input:
            return self.async_show_form(
                step_id="geography_by_name", data_schema=GEOGRAPHY_NAME_SCHEMA
            )

        return await self._async_init_geography(
            user_input, INTEGRATION_TYPE_GEOGRAPHY_NAME
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._entry_data_for_reauth = entry_data
        self._geo_id = async_get_geography_id(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=API_KEY_DATA_SCHEMA
            )

        conf = {**self._entry_data_for_reauth, CONF_API_KEY: user_input[CONF_API_KEY]}

        return await self._async_finish_geography(
            conf, self._entry_data_for_reauth[CONF_INTEGRATION_TYPE]
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=PICK_INTEGRATION_TYPE_SCHEMA
            )

        if user_input["type"] == INTEGRATION_TYPE_GEOGRAPHY_COORDS:
            return await self.async_step_geography_by_coords()
        return await self.async_step_geography_by_name()
