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
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TimeSelector,
)

from .const import (
    CONF_FROM,
    CONF_ROUTES,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
    INTEGRATION_TITLE,
)

_LOGGER = logging.getLogger(__name__)


class NSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nederlandse Spoorwegen."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _validate_api_key(self, api_key: str) -> dict[str, str]:
        """Validate the API key by testing connection to NS API.

        Returns a dict of errors, empty if validation successful.
        """
        errors: dict[str, str] = {}
        client = NSAPI(api_key)
        try:
            await self.hass.async_add_executor_job(client.get_stations)
        except HTTPError:
            errors["base"] = "invalid_auth"
        except (RequestsConnectionError, Timeout):
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception validating API key")
            errors["base"] = "unknown"
        return errors

    def _is_api_key_already_configured(
        self, api_key: str, exclude_entry_id: str | None = None
    ) -> dict[str, str]:
        """Check if the API key is already configured in another entry.

        Args:
            api_key: The API key to check.
            exclude_entry_id: Optional entry ID to exclude from the check.

        Returns:
            A dict of errors, empty if not already configured.
        """
        for entry in self._async_current_entries():
            if (
                entry.entry_id != exclude_entry_id
                and entry.data.get(CONF_API_KEY) == api_key
            ):
                return {"base": "already_configured"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow (API key)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            errors = await self._validate_api_key(user_input[CONF_API_KEY])
            if not errors:
                return self.async_create_entry(
                    title=INTEGRATION_TITLE,
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration to update the API key from the UI."""
        errors: dict[str, str] = {}

        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Check if this API key is already used by another entry
            errors = self._is_api_key_already_configured(
                user_input[CONF_API_KEY], exclude_entry_id=reconfigure_entry.entry_id
            )

            if not errors:
                errors = await self._validate_api_key(user_input[CONF_API_KEY])
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        self._async_abort_entries_match({CONF_API_KEY: import_data[CONF_API_KEY]})

        client = NSAPI(import_data[CONF_API_KEY])
        try:
            stations = await self.hass.async_add_executor_job(client.get_stations)
        except HTTPError:
            return self.async_abort(reason="invalid_auth")
        except (RequestsConnectionError, Timeout):
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception validating API key")
            return self.async_abort(reason="unknown")

        station_codes = {station.code for station in stations}

        subentries: list[ConfigSubentryData] = []
        for route in import_data.get(CONF_ROUTES, []):
            # Convert station codes to uppercase for consistency with UI routes
            for key in (CONF_FROM, CONF_TO, CONF_VIA):
                if key in route:
                    route[key] = route[key].upper()
                    if route[key] not in station_codes:
                        return self.async_abort(reason="invalid_station")

            subentries.append(
                ConfigSubentryData(
                    title=route[CONF_NAME],
                    subentry_type="route",
                    data=route,
                    unique_id=None,
                )
            )

        return self.async_create_entry(
            title=INTEGRATION_TITLE,
            data={CONF_API_KEY: import_data[CONF_API_KEY]},
            subentries=subentries,
        )

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
