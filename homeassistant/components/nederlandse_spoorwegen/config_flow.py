"""Config flow for Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .api import NSAPIAuthError, NSAPIConnectionError, NSAPIError, NSAPIWrapper
from .const import (
    CONF_FROM,
    CONF_NAME,
    CONF_ROUTES,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
)
from .utils import normalize_and_validate_time_format, normalize_station_code

_LOGGER = logging.getLogger(__name__)


async def validate_api_key(hass: HomeAssistant, api_key: str) -> bool:
    """Validate the API key by attempting to validate it."""
    try:
        api_wrapper = NSAPIWrapper(hass, api_key)
        return await api_wrapper.validate_api_key()
    except NSAPIAuthError:
        return False
    except NSAPIConnectionError:
        return False
    except NSAPIError:
        return False


class NSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nederlandse Spoorwegen."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return NSOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]

            # Validate API key
            if await validate_api_key(self.hass, api_key):
                # Set unique ID to prevent multiple entries
                await self.async_set_unique_id("nederlandse_spoorwegen")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Nederlandse Spoorwegen",
                    data={CONF_API_KEY: api_key},
                )

            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        entry_id = self.context.get("entry_id")
        if not entry_id:
            return self.async_abort(reason="no_longer_present")

        config_entry = self.hass.config_entries.async_get_entry(entry_id)
        if config_entry is None:
            return self.async_abort(reason="no_longer_present")

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]

            # Validate new API key
            if await validate_api_key(self.hass, api_key):
                return self.async_update_reload_and_abort(
                    config_entry,
                    data_updates={CONF_API_KEY: api_key},
                )

            errors = {"base": "invalid_auth"}
        else:
            errors = {}

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_KEY, default=config_entry.data.get(CONF_API_KEY, "")
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        # Check if we already have an entry for this integration
        existing_entries = self._async_current_entries()
        if existing_entries:
            _LOGGER.warning(
                "Nederlandse Spoorwegen integration already configured. "
                "Please remove the YAML configuration from your configuration.yaml file"
            )
            return self.async_abort(reason="already_configured")

        if CONF_API_KEY not in import_data:
            return self.async_abort(reason="no_api_key")

        # Validate API key
        api_key = import_data[CONF_API_KEY]
        if not await validate_api_key(self.hass, api_key):
            return self.async_abort(reason="invalid_api_key")

        # Create the main config entry with routes in options
        routes_data = import_data.get(CONF_ROUTES, [])

        _LOGGER.info(
            "Successfully imported Nederlandse Spoorwegen configuration. "
            "Please remove the 'nederlandse_spoorwegen' configuration from your YAML file"
        )

        return self.async_create_entry(
            title="Nederlandse Spoorwegen",
            data={CONF_API_KEY: api_key},
            options={CONF_ROUTES: routes_data},
        )


class NSOptionsFlow(OptionsFlow):
    """Handle options flow for Nederlandse Spoorwegen."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_route_management()

    async def async_step_route_management(self, user_input=None) -> ConfigFlowResult:
        """Handle route management."""
        if user_input is not None:
            if user_input.get("action") == "add_route":
                return await self.async_step_add_route()
            if user_input.get("action") == "remove_route":
                return await self.async_step_remove_route()

        # Show current routes and options
        current_routes = self.config_entry.options.get(CONF_ROUTES, [])
        route_count = len(current_routes)

        return self.async_show_form(
            step_id="route_management",
            data_schema=vol.Schema(
                {
                    vol.Optional("action"): selector.selector(
                        {
                            "select": {
                                "options": [
                                    {"value": "add_route", "label": "Add a new route"},
                                    {
                                        "value": "remove_route",
                                        "label": "Remove an existing route",
                                    },
                                ]
                            }
                        }
                    ),
                }
            ),
            description_placeholders={
                "current_routes": str(route_count),
            },
        )

    async def async_step_add_route(self, user_input=None) -> ConfigFlowResult:
        """Handle adding a new route."""
        errors = {}

        if user_input is not None:
            # Validate route data
            errors = await self._validate_route_input(user_input)

            if not errors:
                # Save the route
                current_routes = list(self.config_entry.options.get(CONF_ROUTES, []))

                # Create route configuration
                route_config = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_FROM: normalize_station_code(user_input[CONF_FROM]),
                    CONF_TO: normalize_station_code(user_input[CONF_TO]),
                }

                if user_input.get(CONF_VIA):
                    route_config[CONF_VIA] = normalize_station_code(
                        user_input[CONF_VIA]
                    )

                if user_input.get(CONF_TIME):
                    _, normalized_time = normalize_and_validate_time_format(
                        user_input[CONF_TIME]
                    )
                    if normalized_time:
                        route_config[CONF_TIME] = normalized_time

                # Add route to the list
                current_routes.append(route_config)

                # Update the config entry options and reload
                self.hass.config_entries.async_update_entry(
                    self.config_entry, options={CONF_ROUTES: current_routes}
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        # Show add route form with station dropdowns
        try:
            station_options = await self._get_station_options()
            if not station_options:
                errors["base"] = "no_stations_available"
                data_schema = vol.Schema({})
            else:
                data_schema = vol.Schema(
                    {
                        vol.Required(CONF_NAME): str,
                        vol.Required(CONF_FROM): selector.selector(
                            {"select": {"options": station_options}}
                        ),
                        vol.Required(CONF_TO): selector.selector(
                            {"select": {"options": station_options}}
                        ),
                        vol.Optional(CONF_VIA): selector.selector(
                            {"select": {"options": station_options}}
                        ),
                        vol.Optional(CONF_TIME): str,
                    }
                )
        except Exception:  # noqa: BLE001  # Allowed in config flows for robustness
            errors["base"] = "unknown"
            data_schema = vol.Schema({})

        return self.async_show_form(
            step_id="add_route",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_remove_route(self, user_input=None) -> ConfigFlowResult:
        """Handle removing a route."""
        current_routes = list(self.config_entry.options.get(CONF_ROUTES, []))

        if not current_routes:
            return await self.async_step_route_management()

        if user_input is not None:
            route_index = user_input.get("route_to_remove")
            if route_index is not None and 0 <= int(route_index) < len(current_routes):
                del current_routes[int(route_index)]

                # Update the config entry options and reload
                self.hass.config_entries.async_update_entry(
                    self.config_entry, options={CONF_ROUTES: current_routes}
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        # Show route removal form
        route_options = []
        for i, route_data in enumerate(current_routes):
            route_name = route_data.get(
                CONF_NAME, f"{route_data[CONF_FROM]} → {route_data[CONF_TO]}"
            )
            route_options.append({"value": str(i), "label": route_name})

        return self.async_show_form(
            step_id="remove_route",
            data_schema=vol.Schema(
                {
                    vol.Required("route_to_remove"): selector.selector(
                        {"select": {"options": route_options}}
                    ),
                }
            ),
        )

    async def _validate_route_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate route input and return errors."""
        errors: dict[str, str] = {}

        try:
            # Field validation
            if (
                not user_input.get(CONF_NAME)
                or not user_input.get(CONF_FROM)
                or not user_input.get(CONF_TO)
            ):
                errors["base"] = "missing_fields"
                return errors

            if user_input.get(CONF_FROM) == user_input.get(CONF_TO):
                errors["base"] = "same_station"
                return errors

            # Time validation
            if user_input.get(CONF_TIME):
                time_valid, _ = normalize_and_validate_time_format(
                    user_input[CONF_TIME]
                )
                if not time_valid:
                    errors[CONF_TIME] = "invalid_time_format"

        except Exception:  # noqa: BLE001  # Allowed in config flows for robustness
            errors["base"] = "unknown"

        return errors

    async def _get_station_options(self) -> list[dict[str, str]]:
        """Get the list of station options for dropdowns, sorted by name."""
        try:
            api_wrapper = NSAPIWrapper(self.hass, self.config_entry.data[CONF_API_KEY])
            stations = await api_wrapper.get_stations()

            if not stations:
                return []

            # Build station mapping
            station_mapping = api_wrapper.build_station_mapping(stations)

            # Convert to dropdown options with station names as labels and codes as values
            station_options = [
                {"value": code, "label": name} for code, name in station_mapping.items()
            ]

            # Sort by label (station name)
            station_options.sort(key=lambda x: x["label"])

        except (NSAPIAuthError, NSAPIConnectionError, NSAPIError):
            return []
        except Exception:  # noqa: BLE001  # Allowed in config flows for robustness
            return []
        else:
            return station_options
