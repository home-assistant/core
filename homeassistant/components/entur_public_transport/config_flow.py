"""Config flow for the Entur public transport integration."""

from typing import Any, override

import probatio

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    FlowType,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .api import (
    EnturApiError,
    EnturRoute,
    EnturStopPlace,
    async_get_stop_routes,
    async_search_stop_places,
)
from .const import (
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_QUERY,
    CONF_SHOW_ON_MAP,
    CONF_STOP_ID,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DEFAULT_NAME,
    DOMAIN,
    SUBENTRY_TYPE_STOP_PLACE,
)


class EnturConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entur public transport."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._places: tuple[EnturStopPlace, ...] = ()
        self._routes: tuple[EnturRoute, ...] = ()
        self._route_error = False
        self._selected_place: EnturStopPlace | None = None
        self._selected_line_whitelist: list[str] = []

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentries supported by Entur."""
        return {SUBENTRY_TYPE_STOP_PLACE: EnturStopPlaceSubentryFlow}

    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Start the first stop place subentry after UI setup."""
        if self.source != SOURCE_USER or self._selected_place is None:
            return result

        subentry_result = await self.hass.config_entries.subentries.async_init(
            (
                result["result"].entry_id,
                SUBENTRY_TYPE_STOP_PLACE,
            ),
            context={"source": SOURCE_USER},
            data={
                "place": self._selected_place,
                "routes": self._routes,
                CONF_WHITELIST_LINES: self._selected_line_whitelist,
            },
        )
        result["next_flow"] = (
            FlowType.CONFIG_SUBENTRIES_FLOW,
            subentry_result["flow_id"],
        )
        return result

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input[CONF_QUERY].strip()
            if len(query) < 2:
                errors["base"] = "query_too_short"
            else:
                try:
                    self._places = await async_search_stop_places(self.hass, query)
                except EnturApiError:
                    errors["base"] = "cannot_connect"
                else:
                    if not self._places:
                        errors["base"] = "no_results"
                    else:
                        return await self.async_step_select_stop()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_QUERY): TextSelector()}
            ),
            errors=errors,
        )

    @override
    async def async_step_select_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select a stop place from the search results."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_id = user_input[CONF_STOP_ID]
            self._selected_place = next(
                (place for place in self._places if place.stop_id == stop_id), None
            )
            if self._selected_place is None:
                errors["base"] = "invalid_selection"
            else:
                try:
                    self._routes = await async_get_stop_routes(
                        self.hass, self._selected_place.stop_id
                    )
                except EnturApiError:
                    self._route_error = True
                if self._routes:
                    return await self.async_step_select_routes()
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="select_stop",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_STOP_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": place.stop_id, "label": place.selection_label}
                                for place in self._places
                            ]
                        )
                    )
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_select_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select the routes to show for the stop place."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        if user_input is not None:
            self._selected_line_whitelist = user_input.get(CONF_WHITELIST_LINES, [])
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="select_routes",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_WHITELIST_LINES, default=[]): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {
                                    "value": route.line_id,
                                    "label": route.selection_label,
                                }
                                for route in self._routes
                            ],
                            multiple=True,
                        )
                    )
                }
            ),
        )

    @override
    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the selected stop place before creating the entry."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        if user_input is not None:
            if not self._routes:
                self._selected_line_whitelist = _parse_line_whitelist(
                    user_input.get(CONF_WHITELIST_LINES, "")
                )
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data=_entry_data([]),
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=_confirm_schema(not self._routes),
            description_placeholders=_place_description(
                self._selected_place,
                route_status=_route_status(self._routes, self._route_error),
            ),
        )

    @override
    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import an Entur platform configuration from YAML."""
        data = dict(import_data)
        data.pop("platform", None)
        stop_ids = data[CONF_STOP_IDS]
        for key, value in _entry_data(stop_ids).items():
            data.setdefault(key, value)
        data[CONF_NAME] = import_data.get(CONF_NAME, DEFAULT_NAME)
        return self.async_create_entry(
            title=data[CONF_NAME],
            data=data,
        )


def _entry_data(stop_ids: list[str]) -> dict[str, Any]:
    """Return default config entry data for a set of stops."""
    return {
        CONF_NAME: DEFAULT_NAME,
        CONF_STOP_IDS: stop_ids,
        CONF_EXPAND_PLATFORMS: True,
        CONF_SHOW_ON_MAP: False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }


def _parse_line_whitelist(value: str | list[str]) -> list[str]:
    """Parse line IDs entered one per line or separated by commas."""
    values = value if isinstance(value, list) else value.replace(",", "\n").splitlines()
    return list(dict.fromkeys(line.strip() for line in values if line.strip()))


class EnturStopPlaceSubentryFlow(ConfigSubentryFlow):
    """Handle adding and reconfiguring one Entur stop place."""

    def __init__(self) -> None:
        """Initialize the stop place subentry flow."""
        self._places: tuple[EnturStopPlace, ...] = ()
        self._routes: tuple[EnturRoute, ...] = ()
        self._route_error = False
        self._selected_place: EnturStopPlace | None = None
        self._selected_line_whitelist: list[str] = []
        self._initial_setup = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a stop place to an existing Entur entry."""
        if user_input and isinstance(user_input.get("place"), EnturStopPlace):
            place = user_input["place"]
            if _stop_is_configured(self._get_entry(), place.stop_id):
                return self.async_abort(reason="already_configured")
            self._selected_place = place
            self._routes = tuple(user_input.get("routes", ()))
            self._selected_line_whitelist = user_input.get(CONF_WHITELIST_LINES, [])
            self._initial_setup = True
            return await self.async_step_confirm()

        return await self._async_step_search("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure an existing stop place."""
        return await self._async_step_search("reconfigure", user_input)

    async def _async_step_search(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        """Search for stop places."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input[CONF_QUERY].strip()
            if len(query) < 2:
                errors["base"] = "query_too_short"
            else:
                try:
                    self._places = await async_search_stop_places(self.hass, query)
                except EnturApiError:
                    errors["base"] = "cannot_connect"
                else:
                    if not self._places:
                        errors["base"] = "no_results"
                    else:
                        return await self.async_step_select_stop()

        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {probatio.Required(CONF_QUERY): TextSelector()}
            ),
            errors=errors,
        )

    async def async_step_select_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select one result from the search."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_id = user_input[CONF_STOP_ID]
            self._selected_place = next(
                (place for place in self._places if place.stop_id == stop_id), None
            )
            if self._selected_place is None:
                errors["base"] = "invalid_selection"
            else:
                try:
                    self._routes = await async_get_stop_routes(
                        self.hass, self._selected_place.stop_id
                    )
                except EnturApiError:
                    self._route_error = True
                if self._routes:
                    return await self.async_step_select_routes()
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="select_stop",
            data_schema=_stop_selector_schema(self._places),
            errors=errors,
        )

    async def async_step_select_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select routes to show for the stop place."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        if user_input is not None:
            self._selected_line_whitelist = user_input.get(CONF_WHITELIST_LINES, [])
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="select_routes",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_WHITELIST_LINES, default=[]): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {
                                    "value": route.line_id,
                                    "label": route.selection_label,
                                }
                                for route in self._routes
                            ],
                            multiple=True,
                        )
                    )
                }
            ),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Confirm the stop place and configure its optional line filter."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        if user_input is not None:
            line_whitelist = self._selected_line_whitelist
            if not self._routes and not self._initial_setup:
                line_whitelist = _parse_line_whitelist(
                    user_input.get(CONF_WHITELIST_LINES, "")
                )
            entry = self._get_entry()
            if _stop_is_configured(
                entry,
                self._selected_place.stop_id,
                exclude_subentry_id=(
                    self._reconfigure_subentry_id
                    if self.source == SOURCE_RECONFIGURE
                    else None
                ),
            ):
                return self.async_abort(reason="already_configured")

            data = {
                CONF_STOP_ID: self._selected_place.stop_id,
                CONF_WHITELIST_LINES: line_whitelist,
            }
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_and_abort(
                    entry,
                    self._get_reconfigure_subentry(),
                    title=self._selected_place.name,
                    data=data,
                    unique_id=self._selected_place.stop_id,
                )
            return self.async_create_entry(
                title=self._selected_place.name,
                data=data,
                unique_id=self._selected_place.stop_id,
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=_confirm_schema(not self._routes and not self._initial_setup),
            description_placeholders=_place_description(
                self._selected_place,
                route_status=_route_status(self._routes, self._route_error),
            ),
        )


def _stop_selector_schema(
    places: tuple[EnturStopPlace, ...],
) -> probatio.Schema:
    """Build a selector schema for stop places."""
    return probatio.Schema(
        {
            probatio.Required(CONF_STOP_ID): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": place.stop_id, "label": place.selection_label}
                        for place in places
                    ]
                )
            )
        }
    )


def _confirm_schema(include_manual_line_ids: bool) -> probatio.Schema:
    """Build the confirmation schema."""
    if not include_manual_line_ids:
        return probatio.Schema({})
    return probatio.Schema(
        {
            probatio.Optional(CONF_WHITELIST_LINES, default=""): TextSelector(
                {"multiline": True}
            )
        }
    )


def _route_status(routes: tuple[EnturRoute, ...], route_error: bool) -> str:
    """Return a user-facing route loading status."""
    if routes:
        return "Choose the routes you want to show for this stop place."
    if route_error:
        return "The route list could not be loaded. Leave the filter empty to show all routes, or enter line IDs manually."
    return "No routes were returned. Leave the filter empty to show all routes, or enter line IDs manually."


def _place_description(place: EnturStopPlace, route_status: str) -> dict[str, str]:
    """Build confirmation placeholders for a stop place."""
    return {
        "name": place.name,
        "display_name": place.display_name,
        "locality": place.locality or "Unknown",
        "transport_modes": ", ".join(place.transport_modes) or "Unknown",
        "route_status": route_status,
        "stop_id": place.stop_id,
        "role": (
            "transport hub" if place.role == "parent" else "standalone stop place"
        ),
        "entur_url": place.entur_url,
    }


def _stop_is_configured(
    entry: ConfigEntry,
    stop_id: str,
    exclude_subentry_id: str | None = None,
) -> bool:
    """Return whether a stop is already configured on the entry."""
    if stop_id in entry.data.get(CONF_STOP_IDS, []):
        return True
    return any(
        subentry.subentry_type == SUBENTRY_TYPE_STOP_PLACE
        and subentry.subentry_id != exclude_subentry_id
        and subentry.data.get(CONF_STOP_ID) == stop_id
        for subentry in entry.subentries.values()
    )
