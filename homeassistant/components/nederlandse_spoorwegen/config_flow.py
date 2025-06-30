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
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nederlandse Spoorwegen."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        _LOGGER.debug("Initializing NSConfigFlow")
        self._api_key: str | None = None
        self._routes: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow (API key)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            masked_api_key = (
                api_key[:3] + "***" + api_key[-2:] if len(api_key) > 5 else "***"
            )
            _LOGGER.debug("User provided API key: %s", masked_api_key)
            # Abort if an entry with this API key already exists
            await self.async_set_unique_id(api_key)
            self._abort_if_unique_id_configured()
            self._api_key = api_key
            return await self.async_step_routes()

        _LOGGER.debug("Showing API key form to user")
        data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "station_list_url": "https://nl.wikipedia.org/wiki/Lijst_van_spoorwegstations_in_Nederland"
            },
        )

    async def async_step_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step to add routes."""
        errors: dict[str, str] = {}
        ROUTE_SCHEMA = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required("from"): str,
                vol.Required("to"): str,
                vol.Optional("via"): str,
                vol.Optional("time"): str,
            }
        )
        if user_input is not None:
            _LOGGER.debug("User provided route: %s", user_input)
            self._routes.append(user_input)
            # For simplicity, allow adding one route for now, or finish
            return self.async_create_entry(
                title="Nederlandse Spoorwegen",
                data={CONF_API_KEY: self._api_key, "routes": self._routes},
            )
        _LOGGER.debug("Showing route form to user")
        return self.async_show_form(
            step_id="routes",
            data_schema=ROUTE_SCHEMA,
            errors=errors,
            description_placeholders={
                "station_list_url": "https://nl.wikipedia.org/wiki/Lijst_van_spoorwegstations_in_Nederland"
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> NSOptionsFlowHandler:
        """Return the options flow handler for this config entry."""
        return NSOptionsFlowHandler(config_entry)


class NSOptionsFlowHandler(OptionsFlow):
    """Options flow handler for Nederlandse Spoorwegen integration."""

    def __init__(self, config_entry) -> None:
        """Initialize the options flow handler."""
        super().__init__()
        self._config_entry = config_entry
        self._action = None  # Persist action across steps
        self._edit_idx = None  # Initialize edit index attribute

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Show the default options flow step for Home Assistant compatibility."""
        return await self.async_step_options_init(user_input)

    async def async_step_options_init(self, user_input=None) -> ConfigFlowResult:
        """Show a screen to choose add, edit, or delete route."""
        errors: dict[str, str] = {}
        ACTIONS = {
            "add": "Add route",
            "edit": "Edit route",
            "delete": "Delete route",
        }
        data_schema = vol.Schema({vol.Required("action"): vol.In(ACTIONS)})
        _LOGGER.debug(
            "Options flow: async_step_options_init called with user_input=%s",
            user_input,
        )
        if user_input is not None:
            action = user_input["action"]
            self._action = action  # Store action for later steps
            _LOGGER.debug("Options flow: action selected: %s", action)
            if action == "add":
                return await self.async_step_add_route()
            if action == "edit":
                return await self.async_step_select_route({"action": "edit"})
            if action == "delete":
                return await self.async_step_select_route({"action": "delete"})
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_select_route(self, user_input=None) -> ConfigFlowResult:
        """Show a screen to select a route for edit or delete."""
        errors: dict[str, str] = {}
        routes = (
            self._config_entry.options.get("routes")
            or self._config_entry.data.get("routes")
            or []
        )
        # Use self._action if not present in user_input
        action = (
            user_input.get("action")
            if user_input and "action" in user_input
            else self._action
        )
        route_summaries = [
            f"{route.get('name', f'Route {i + 1}')}: {route.get('from', '?')} → {route.get('to', '?')}"
            + (f" [{route.get('time')} ]" if route.get("time") else "")
            for i, route in enumerate(routes)
        ]
        if not routes:
            errors["base"] = "no_routes"
            return await self.async_step_init()
        data_schema = vol.Schema(
            {
                vol.Required("route_idx"): vol.In(
                    {str(i): s for i, s in enumerate(route_summaries)}
                )
            }
        )
        _LOGGER.debug(
            "Options flow: async_step_select_route called with user_input=%s",
            user_input,
        )
        _LOGGER.debug("Options flow: action=%s, routes=%s", action, routes)
        if user_input is not None and "route_idx" in user_input:
            _LOGGER.debug(
                "Options flow: route_idx selected: %s", user_input["route_idx"]
            )
            idx = int(user_input["route_idx"])
            if action == "edit":
                # Go to edit form for this route
                return await self.async_step_edit_route({"idx": idx})
            if action == "delete":
                # Remove the route and save
                routes = routes.copy()
                routes.pop(idx)
                return self.async_create_entry(title="", data={"routes": routes})
        return self.async_show_form(
            step_id="select_route",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"action": action or "manage"},
        )

    async def async_step_add_route(self, user_input=None) -> ConfigFlowResult:
        """Show a form to add a new route."""
        errors: dict[str, str] = {}
        ROUTE_SCHEMA = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required("from"): str,
                vol.Required("to"): str,
                vol.Optional("via"): str,
                vol.Optional("time"): str,
            }
        )
        routes = (
            self._config_entry.options.get("routes")
            or self._config_entry.data.get("routes")
            or []
        )
        _LOGGER.debug(
            "Options flow: async_step_add_route called with user_input=%s", user_input
        )
        if user_input is not None and any(user_input.values()):
            _LOGGER.debug("Options flow: adding route: %s", user_input)
            # Validate required fields
            if (
                not user_input.get("name")
                or not user_input.get("from")
                or not user_input.get("to")
            ):
                errors["base"] = "missing_fields"
            else:
                routes = routes.copy()
                routes.append(user_input)
                return self.async_create_entry(title="", data={"routes": routes})
        return self.async_show_form(
            step_id="add_route",
            data_schema=ROUTE_SCHEMA,
            errors=errors,
            description_placeholders={
                "station_list_url": "https://nl.wikipedia.org/wiki/Lijst_van_spoorwegstations_in_Nederland"
            },
        )

    async def async_step_edit_route(self, user_input=None) -> ConfigFlowResult:
        """Show a form to edit an existing route."""
        errors: dict[str, str] = {}
        routes = (
            self._config_entry.options.get("routes")
            or self._config_entry.data.get("routes")
            or []
        )
        # Store idx on first call, use self._edit_idx on submit
        if user_input is not None and "idx" in user_input:
            idx = user_input["idx"]
            self._edit_idx = idx
        else:
            idx = getattr(self, "_edit_idx", None)
        if idx is None or not (0 <= idx < len(routes)):
            errors["base"] = "invalid_route_index"
            return await self.async_step_options_init()
        route = routes[idx]
        ROUTE_SCHEMA = vol.Schema(
            {
                vol.Required("name", default=route.get("name", "")): str,
                vol.Required("from", default=route.get("from", "")): str,
                vol.Required("to", default=route.get("to", "")): str,
                vol.Optional("via", default=route.get("via", "")): str,
                vol.Optional("time", default=route.get("time", "")): str,
            }
        )
        _LOGGER.debug(
            "Options flow: async_step_edit_route called with user_input=%s", user_input
        )
        if user_input is not None and any(
            k in user_input for k in ("name", "from", "to")
        ):
            _LOGGER.debug(
                "Options flow: editing route idx=%s with data=%s", idx, user_input
            )
            # Validate required fields
            if (
                not user_input.get("name")
                or not user_input.get("from")
                or not user_input.get("to")
            ):
                errors["base"] = "missing_fields"
            else:
                routes = routes.copy()
                routes[idx] = {
                    "name": user_input["name"],
                    "from": user_input["from"],
                    "to": user_input["to"],
                    "via": user_input.get("via", ""),
                    "time": user_input.get("time", ""),
                }
                # Clean up idx after edit
                if hasattr(self, "_edit_idx"):
                    del self._edit_idx
                return self.async_create_entry(title="", data={"routes": routes})
        return self.async_show_form(
            step_id="edit_route",
            data_schema=ROUTE_SCHEMA,
            errors=errors,
            description_placeholders={
                "station_list_url": "https://nl.wikipedia.org/wiki/Lijst_van_spoorwegstations_in_Nederland"
            },
        )
