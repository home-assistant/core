"""Config flow for Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging
from typing import Any

from ns_api import NSAPI, Station
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    HTTPError,
    Timeout,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TimeSelector,
)

from .api import NSAPIAuthError, NSAPIConnectionError
from .const import CONF_FROM, CONF_NAME, CONF_TIME, CONF_TO, CONF_VIA, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nederlandse Spoorwegen."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow (API key)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = NSAPI(user_input[CONF_API_KEY])
            try:
                await self.hass.async_add_executor_job(client.get_stations)
            except NSAPIAuthError:
                errors["base"] = "invalid_auth"
            except NSAPIConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception validating API key")
                errors["base"] = "unknown"
            if not errors:
                return self.async_create_entry(
                    title="Nederlandse Spoorwegen",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    # async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
    #     """Handle import from YAML configuration."""
    #     _LOGGER.debug("Importing YAML configuration: %s", import_data)
    #
    #     # Check if we already have an entry for this integration
    #     existing_entries = self._async_current_entries()
    #     if existing_entries:
    #         _LOGGER.warning("Integration already configured, skipping YAML import")
    #         return self.async_abort(reason="already_configured")
    #
    #     # The sensor platform should pass the platform config directly
    #     # This contains: api_key, routes (list)
    #     if CONF_API_KEY not in import_data:
    #         _LOGGER.error(
    #             "No API key found in YAML import data "
    #             "Expected sensor platform configuration with api_key"
    #         )
    #         return self.async_abort(reason="unknown")
    #
    #     # Validate API key
    #     api_key = import_data[CONF_API_KEY]
    #     api_wrapper = NSAPIWrapper(self.hass, api_key)
    #
    #     try:
    #         if not await api_wrapper.validate_api_key():
    #             _LOGGER.error("Invalid API key in YAML configuration")
    #             return self.async_abort(reason="invalid_api_key")
    #     except (NSAPIAuthError, NSAPIConnectionError, NSAPIError) as err:
    #         _LOGGER.error("Failed to validate API key during import: %s", err)
    #         return self.async_abort(reason="cannot_connect")
    #
    #     # Create the main config entry
    #     await self.async_set_unique_id(f"{DOMAIN}")
    #     self._abort_if_unique_id_configured()
    #
    #     # Extract routes from sensor platform config
    #     routes = import_data.get(CONF_ROUTES, [])
    #     if routes:
    #         _LOGGER.info(
    #             "Importing %d routes from sensor platform YAML configuration",
    #             len(routes),
    #         )
    #         # Store routes in the entry data for migration
    #         config_entry = self.async_create_entry(
    #             title="Nederlandse Spoorwegen",
    #             data={
    #                 CONF_API_KEY: api_key,
    #                 CONF_ROUTES: routes,  # Will be migrated to subentries in async_setup_entry
    #             },
    #         )
    #     else:
    #         _LOGGER.info(
    #             "No routes found in YAML configuration, creating entry with API key only"
    #         )
    #         config_entry = self.async_create_entry(
    #             title="Nederlandse Spoorwegen",
    #             data={CONF_API_KEY: api_key},
    #         )
    #
    #     return config_entry

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"route": RouteSubentryFlowHandler}


class RouteSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying routes."""

    def __init__(self) -> None:
        """Initialize route subentry flow."""
        self.stations: dict[str, Station] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new route subentry."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        client = NSAPI(self._get_entry().data[CONF_API_KEY])
        if not self.stations:
            try:
                self.stations = {
                    station.code: station
                    for station in await self.hass.async_add_executor_job(
                        client.get_stations
                    )
                }
            except (RequestsConnectionError, Timeout, HTTPError, ValueError):
                return self.async_abort(reason="cannot_connect")

        options = [
            SelectOptionDict(label=station.names["long"], value=code)
            for code, station in self.stations.items()
        ]
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(CONF_FROM): SelectSelector(
                        SelectSelectorConfig(options=options, sort=True),
                    ),
                    vol.Required(CONF_TO): SelectSelector(
                        SelectSelectorConfig(options=options, sort=True),
                    ),
                    vol.Optional(CONF_VIA): SelectSelector(
                        SelectSelectorConfig(options=options, sort=True),
                    ),
                    vol.Optional(CONF_TIME): TimeSelector(),
                }
            ),
        )
