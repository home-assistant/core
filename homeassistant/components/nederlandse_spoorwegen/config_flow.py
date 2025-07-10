"""Config flow for Nederlandse Spoorwegen integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast
import uuid

from ns_api import NSAPI
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    CONF_ACTION,
    CONF_FROM,
    CONF_NAME,
    CONF_ROUTE_IDX,
    CONF_TIME,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
    STATION_LIST_URL,
)

_LOGGER = logging.getLogger(__name__)


class NSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nederlandse Spoorwegen."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        # Only log flow initialization at debug level
        _LOGGER.debug("NSConfigFlow initialized")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow (API key)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            # Only log API key validation attempt
            _LOGGER.debug("Validating user API key for NS integration")
            try:
                client = NSAPI(api_key)
                await self.hass.async_add_executor_job(client.get_stations)
            except (ValueError, ConnectionError, TimeoutError, Exception) as ex:
                _LOGGER.debug("API validation failed: %s", ex)
                if (
                    "401" in str(ex)
                    or "unauthorized" in str(ex).lower()
                    or "invalid" in str(ex).lower()
                ):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            if not errors:
                await self.async_set_unique_id(api_key)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Nederlandse Spoorwegen",
                    data={CONF_API_KEY: api_key},
                    options={"routes": []},
                )
        data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"station_list_url": STATION_LIST_URL},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> NSOptionsFlowHandler:
        """Return the options flow handler for this config entry."""
        return NSOptionsFlowHandler(config_entry)

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication step for updating API key."""
        errors: dict[str, str] = {}
        entry = self.context.get("entry")
        if entry is None and "entry_id" in self.context:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None and entry is not None:
            entry = cast(ConfigEntry, entry)
            api_key = user_input.get(CONF_API_KEY)
            if not api_key:
                errors[CONF_API_KEY] = "missing_fields"
            else:
                _LOGGER.debug("Reauth: User provided new API key for NS integration")
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )
                return self.async_abort(reason="reauth_successful")
        data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(
            step_id="reauth",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration step for updating API key."""
        errors: dict[str, str] = {}
        entry = self.context.get("entry")
        if entry is None and "entry_id" in self.context:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None and entry is not None:
            entry = cast(ConfigEntry, entry)
            api_key = user_input.get(CONF_API_KEY)
            if not api_key:
                errors[CONF_API_KEY] = "missing_fields"
            else:
                _LOGGER.debug(
                    "Reconfigure: User provided new API key for NS integration"
                )
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_API_KEY: api_key}
                )
                return self.async_abort(reason="reconfigure_successful")
        data_schema = vol.Schema({vol.Required(CONF_API_KEY): str})
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )


class NSOptionsFlowHandler(OptionsFlow):
    """Options flow handler for Nederlandse Spoorwegen integration."""

    def __init__(self, config_entry) -> None:
        """Initialize the options flow handler."""
        super().__init__()
        _LOGGER.debug("NS OptionsFlow initialized for entry: %s", config_entry.entry_id)
        self._config_entry = config_entry
        self._action = None
        self._edit_idx = None

    async def _get_station_name_map(self) -> dict[str, str]:
        """Get a mapping of station code to human-friendly name for dropdowns."""
        stations = []
        # Try to get full station objects from runtime_data if available
        if (
            hasattr(self._config_entry, "runtime_data")
            and self._config_entry.runtime_data
        ):
            stations = self._config_entry.runtime_data.get("stations", [])
        if (
            not stations
            and hasattr(self._config_entry, "runtime_data")
            and self._config_entry.runtime_data
        ):
            # Fallback: try to get from coordinator if present
            coordinator = self._config_entry.runtime_data.get("coordinator")
            if coordinator and hasattr(coordinator, "stations"):
                stations = coordinator.stations
        # Build mapping {code: name}
        code_name = {}
        for s in stations:
            code = getattr(s, "code", None) if hasattr(s, "code") else s.get("code")
            name = (
                getattr(s, "names", {}).get("long")
                if hasattr(s, "names")
                else s.get("names", {}).get("long")
            )
            if code and name:
                code_name[code.upper()] = name
        return code_name

    async def _get_station_options(self) -> list[dict[str, str]] | list[str]:
        """Get the list of approved station codes for dropdowns, with names if available, sorted by name."""
        code_name = await self._get_station_name_map()
        if code_name:
            # Sort by station name (label)
            return sorted(
                [{"value": code, "label": name} for code, name in code_name.items()],
                key=lambda x: x["label"].lower(),
            )
        # fallback: just codes, sorted
        codes = (
            self._config_entry.runtime_data.get("approved_station_codes", [])
            if hasattr(self._config_entry, "runtime_data")
            and self._config_entry.runtime_data
            else []
        )
        return sorted(codes)

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Show the default options flow step for Home Assistant compatibility."""
        return await self.async_step_options_init(user_input)

    async def async_step_options_init(self, user_input=None) -> ConfigFlowResult:
        """Show the initial options step for managing routes (add, edit, delete)."""
        errors: dict[str, str] = {}
        ACTIONS = {
            "add": "Add route",
            "edit": "Edit route",
            "delete": "Delete route",
        }
        data_schema = vol.Schema({vol.Required(CONF_ACTION): vol.In(ACTIONS)})
        if user_input is not None:
            action = user_input["action"]
            self._action = action
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
        """Show a form to select a route for editing or deletion."""
        errors: dict[str, str] = {}
        routes = (
            self._config_entry.options.get("routes")
            or self._config_entry.data.get("routes")
            or []
        )
        action = (
            user_input.get(CONF_ACTION)
            if user_input and CONF_ACTION in user_input
            else self._action
        )
        if not routes:
            errors["base"] = "no_routes"
            return await self.async_step_init()
        data_schema = vol.Schema(
            {
                vol.Required(CONF_ROUTE_IDX): vol.In(
                    {
                        str(i): s
                        for i, s in enumerate(
                            [
                                f"{route.get('name', f'Route {i + 1}')}: {route.get('from', '?')} → {route.get('to', '?')}"
                                + (
                                    f" [{route.get('time')} ]"
                                    if route.get("time")
                                    else ""
                                )
                                for i, route in enumerate(routes)
                            ]
                        )
                    }
                )
            }
        )
        if user_input is not None and CONF_ROUTE_IDX in user_input:
            idx = int(user_input[CONF_ROUTE_IDX])
            if action == "edit":
                return await self.async_step_edit_route({"idx": idx})
            if action == "delete":
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
        """Show a form to add a new route to the integration."""
        errors: dict[str, str] = {}
        try:
            station_options = await self._get_station_options()
            if not station_options:
                # Manual entry fallback: use text fields for from/to/via
                ROUTE_SCHEMA = vol.Schema(
                    {
                        vol.Required(CONF_NAME): str,
                        vol.Required(CONF_FROM): str,
                        vol.Required(CONF_TO): str,
                        vol.Optional(CONF_VIA): str,
                        vol.Optional(CONF_TIME): str,
                    }
                )
            else:
                # If station_options is a list of dicts, use as-is; else build list of dicts
                options = (
                    station_options
                    if station_options and isinstance(station_options[0], dict)
                    else [{"value": c, "label": c} for c in station_options]
                )
                ROUTE_SCHEMA = vol.Schema(
                    {
                        vol.Required(CONF_NAME): str,
                        vol.Required(CONF_FROM): selector(
                            {
                                "select": {
                                    "options": options,
                                }
                            }
                        ),
                        vol.Required(CONF_TO): selector(
                            {
                                "select": {
                                    "options": options,
                                }
                            }
                        ),
                        vol.Optional(CONF_VIA): selector(
                            {
                                "select": {
                                    "options": options,
                                    "mode": "dropdown",
                                    "custom_value": True,
                                }
                            }
                        ),
                        vol.Optional(CONF_TIME): str,
                    }
                )
            routes = (
                self._config_entry.options.get("routes")
                or self._config_entry.data.get("routes")
                or []
            )
            if user_input is not None and any(user_input.values()):
                # Only log add action, not full user_input
                _LOGGER.debug("Options flow: adding route")
                # Validate required fields
                if (
                    not user_input.get(CONF_NAME)
                    or not user_input.get(CONF_FROM)
                    or not user_input.get(CONF_TO)
                ):
                    errors["base"] = "missing_fields"
                elif user_input.get(CONF_FROM) == user_input.get(CONF_TO):
                    errors["base"] = "same_station"
                else:
                    routes = routes.copy()
                    # Always store codes in uppercase
                    route_to_add = {
                        "route_id": str(uuid.uuid4()),
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_FROM: user_input[CONF_FROM].upper(),
                        CONF_TO: user_input[CONF_TO].upper(),
                        CONF_VIA: user_input.get(CONF_VIA, "").upper()
                        if user_input.get(CONF_VIA)
                        else "",
                        CONF_TIME: user_input.get(CONF_TIME, ""),
                    }
                    routes.append(route_to_add)
                    return self.async_create_entry(title="", data={"routes": routes})
        except Exception:
            _LOGGER.exception("Exception in async_step_add_route")
            errors["base"] = "unknown"
        return self.async_show_form(
            step_id="add_route",
            data_schema=ROUTE_SCHEMA if "ROUTE_SCHEMA" in locals() else vol.Schema({}),
            errors=errors,
            description_placeholders={"station_list_url": STATION_LIST_URL},
        )

    async def async_step_edit_route(self, user_input=None) -> ConfigFlowResult:
        """Show a form to edit an existing route in the integration."""
        errors: dict[str, str] = {}
        try:
            routes = (
                self._config_entry.options.get("routes")
                or self._config_entry.data.get("routes")
                or []
            )
            station_options = await self._get_station_options()
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
            if not station_options:
                # Manual entry fallback: use text fields for from/to/via
                ROUTE_SCHEMA = vol.Schema(
                    {
                        vol.Required(CONF_NAME, default=route.get(CONF_NAME, "")): str,
                        vol.Required(CONF_FROM, default=route.get(CONF_FROM, "")): str,
                        vol.Required(CONF_TO, default=route.get(CONF_TO, "")): str,
                        vol.Optional(CONF_VIA, default=route.get(CONF_VIA, "")): str,
                        vol.Optional(CONF_TIME, default=route.get(CONF_TIME, "")): str,
                    }
                )
            else:
                options = (
                    station_options
                    if station_options and isinstance(station_options[0], dict)
                    else [{"value": c, "label": c} for c in station_options]
                )
                ROUTE_SCHEMA = vol.Schema(
                    {
                        vol.Required(CONF_NAME, default=route.get(CONF_NAME, "")): str,
                        vol.Required(
                            CONF_FROM, default=route.get(CONF_FROM, "")
                        ): selector(
                            {
                                "select": {
                                    "options": options,
                                }
                            }
                        ),
                        vol.Required(CONF_TO, default=route.get(CONF_TO, "")): selector(
                            {
                                "select": {
                                    "options": options,
                                }
                            }
                        ),
                        vol.Optional(
                            CONF_VIA, default=route.get(CONF_VIA, "")
                        ): selector(
                            {
                                "select": {
                                    "options": options,
                                    "mode": "dropdown",
                                    "custom_value": True,
                                }
                            }
                        ),
                        vol.Optional(CONF_TIME, default=route.get(CONF_TIME, "")): str,
                    }
                )
            if user_input is not None and any(
                k in user_input for k in (CONF_NAME, CONF_FROM, CONF_TO)
            ):
                _LOGGER.debug("Options flow: editing route idx=%s", idx)
                # Validate required fields
                if (
                    not user_input.get(CONF_NAME)
                    or not user_input.get(CONF_FROM)
                    or not user_input.get(CONF_TO)
                ):
                    errors["base"] = "missing_fields"
                else:
                    routes = routes.copy()
                    # Always store codes in uppercase
                    old_route = routes[idx]
                    route_to_edit = {
                        "route_id": old_route.get("route_id", str(uuid.uuid4())),
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_FROM: user_input[CONF_FROM].upper(),
                        CONF_TO: user_input.get(CONF_TO, "").upper(),
                        CONF_VIA: user_input.get(CONF_VIA, "").upper()
                        if user_input.get(CONF_VIA)
                        else "",
                        CONF_TIME: user_input.get(CONF_TIME, ""),
                    }
                    routes[idx] = route_to_edit
                    # Clean up idx after edit
                    if hasattr(self, "_edit_idx"):
                        del self._edit_idx
                    return self.async_create_entry(title="", data={"routes": routes})
        except Exception:
            _LOGGER.exception("Exception in async_step_edit_route")
            errors["base"] = "unknown"
        return self.async_show_form(
            step_id="edit_route",
            data_schema=ROUTE_SCHEMA if "ROUTE_SCHEMA" in locals() else vol.Schema({}),
            errors=errors,
            description_placeholders={"station_list_url": STATION_LIST_URL},
        )
