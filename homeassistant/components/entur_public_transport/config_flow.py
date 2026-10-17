"""Config flow for the Entur public transport integration."""

from typing import Any, override

import probatio

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    FlowType,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .api import (
    EnturApiError,
    EnturQuay,
    EnturRoute,
    EnturStopPlace,
    async_get_stop_place,
    async_get_stop_quays,
    async_get_stop_routes,
    async_search_stop_places,
    format_stop_place_title,
    line_id_label,
)
from .const import (
    CONF_EXPAND_PLATFORMS,
    CONF_MANUAL_WHITELIST_LINES,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_PLATFORM_MODE,
    CONF_QUAY_IDS,
    CONF_QUERY,
    CONF_RECONFIGURE_ACTION,
    CONF_ROUTE_LABELS,
    CONF_STOP_ID,
    CONF_STOP_IDS,
    CONF_STOP_PLACE_METADATA_VERSION,
    CONF_STOP_PLACE_NAME,
    CONF_STOP_PLACE_TYPES,
    CONF_WHITELIST_LINES,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORM_MODE_ALL,
    PLATFORM_MODE_SELECTED,
    PLATFORM_MODE_STOP_PLACE,
    RECONFIGURE_ACTION_EDIT,
    RECONFIGURE_ACTION_REPLACE,
    STOP_PLACE_METADATA_VERSION,
    SUBENTRY_TYPE_STOP_PLACE,
)


class EnturConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entur public transport."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._places: tuple[EnturStopPlace, ...] = ()
        self._routes: tuple[EnturRoute, ...] = ()
        self._quays: tuple[EnturQuay, ...] = ()
        self._selected_place: EnturStopPlace | None = None
        self._selected_line_whitelist: list[str] = []
        self._selected_route_labels: dict[str, str] = {}
        self._selected_platform_mode = PLATFORM_MODE_STOP_PLACE
        self._selected_quay_ids: list[str] = []
        self._selected_show_on_map = False

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentries supported by Entur."""
        return {SUBENTRY_TYPE_STOP_PLACE: EnturStopPlaceSubentryFlow}

    @override
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
                CONF_ROUTE_LABELS: self._selected_route_labels,
                CONF_PLATFORM_MODE: self._selected_platform_mode,
                CONF_QUAY_IDS: self._selected_quay_ids,
                CONF_SHOW_ON_MAP: self._selected_show_on_map,
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
                    self._routes = ()
                try:
                    self._quays = await async_get_stop_quays(
                        self.hass, self._selected_place.stop_id
                    )
                except EnturApiError:
                    self._quays = ()
                return await self.async_step_select_routes()

        return self.async_show_form(
            step_id="select_stop",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_STOP_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                _selection_option(place.stop_id, place.selection_label)
                                for place in self._places
                            ]
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_select_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select the routes to show for the stop place."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        if user_input is not None:
            self._selected_line_whitelist = _combine_line_whitelist(
                user_input.get(CONF_WHITELIST_LINES, []),
                user_input.get(CONF_MANUAL_WHITELIST_LINES, ""),
            )
            self._selected_route_labels = _route_labels(
                self._selected_line_whitelist, self._routes
            )
            return await self.async_step_select_platforms()

        return self.async_show_form(
            step_id="select_routes",
            data_schema=_route_schema(self._routes),
        )

    async def async_step_select_platforms(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select the level of platform detail to add."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        errors: dict[str, str] = {}
        if user_input is not None:
            mode, quay_ids = _platform_selection(user_input, self._quays)
            if mode == PLATFORM_MODE_SELECTED and not quay_ids:
                errors["base"] = "select_platform"
            else:
                self._selected_platform_mode = mode
                self._selected_quay_ids = quay_ids
                self._selected_show_on_map = user_input.get(CONF_SHOW_ON_MAP, False)
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="select_platforms",
            data_schema=_platform_schema(
                self._quays,
                self._selected_platform_mode,
                self._selected_quay_ids,
                self._selected_show_on_map,
            ),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the selected stop place before creating the entry."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data=_entry_data([]),
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=_confirm_schema(),
            description_placeholders=_place_description(self._selected_place),
        )

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


def _combine_line_whitelist(
    selected_line_ids: list[str], manual_line_ids: str
) -> list[str]:
    """Combine API-selected and manually entered line IDs."""
    return _parse_line_whitelist(
        [*selected_line_ids, *manual_line_ids.replace(",", chr(10)).splitlines()]
    )


def _selection_option(value: str, label: str) -> SelectOptionDict:
    """Return a correctly typed selector option."""
    return {"value": value, "label": label}


def _route_schema(
    routes: tuple[EnturRoute, ...],
    selected_line_whitelist: list[str] | None = None,
) -> probatio.Schema:
    """Build the route selection form, including manual line IDs."""
    available_line_ids = {route.line_id for route in routes}
    selected_line_ids = selected_line_whitelist or []
    manual_line_ids = [
        line_id for line_id in selected_line_ids if line_id not in available_line_ids
    ]
    schema: dict[Any, Any] = {
        probatio.Optional(
            CONF_MANUAL_WHITELIST_LINES, default="\n".join(manual_line_ids)
        ): TextSelector({"multiline": True})
    }
    if routes:
        schema = {
            probatio.Optional(
                CONF_WHITELIST_LINES,
                default=[
                    line_id
                    for line_id in selected_line_ids
                    if line_id in available_line_ids
                ],
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        _selection_option(route.line_id, route.selection_label)
                        for route in routes
                    ],
                    multiple=True,
                )
            ),
            **schema,
        }
    return probatio.Schema(schema)


def _platform_schema(
    quays: tuple[EnturQuay, ...],
    selected_mode: str,
    selected_quay_ids: list[str],
    show_on_map: bool,
) -> probatio.Schema:
    """Build the platform detail selector for a stop place."""
    options = [
        PLATFORM_MODE_STOP_PLACE,
        PLATFORM_MODE_ALL,
    ]
    if quays:
        options.append(PLATFORM_MODE_SELECTED)

    schema: dict[Any, Any] = {
        probatio.Required(CONF_PLATFORM_MODE, default=selected_mode): SelectSelector(
            SelectSelectorConfig(
                options=options,
                translation_key=CONF_PLATFORM_MODE,
            )
        ),
        probatio.Optional(CONF_SHOW_ON_MAP, default=show_on_map): BooleanSelector(),
    }
    if quays:
        available_quay_ids = {quay.quay_id for quay in quays}
        schema[
            probatio.Optional(
                CONF_QUAY_IDS,
                default=[
                    quay_id
                    for quay_id in selected_quay_ids
                    if quay_id in available_quay_ids
                ],
            )
        ] = SelectSelector(
            SelectSelectorConfig(
                options=[
                    _selection_option(quay.quay_id, quay.selection_label)
                    for quay in quays
                ],
                multiple=True,
            )
        )
    return probatio.Schema(schema)


def _platform_selection(
    user_input: dict[str, Any], quays: tuple[EnturQuay, ...]
) -> tuple[str, list[str]]:
    """Return a validated platform mode and selected quay IDs."""
    mode = user_input.get(CONF_PLATFORM_MODE)
    if mode not in {
        PLATFORM_MODE_STOP_PLACE,
        PLATFORM_MODE_ALL,
        PLATFORM_MODE_SELECTED,
    }:
        mode = PLATFORM_MODE_STOP_PLACE

    available_quay_ids = {quay.quay_id for quay in quays}
    quay_ids = [
        quay_id
        for quay_id in user_input.get(CONF_QUAY_IDS, [])
        if quay_id in available_quay_ids
    ]
    return mode, list(dict.fromkeys(quay_ids))


class EnturStopPlaceSubentryFlow(ConfigSubentryFlow):
    """Handle adding and reconfiguring one Entur stop place."""

    def __init__(self) -> None:
        """Initialize the stop place subentry flow."""
        self._places: tuple[EnturStopPlace, ...] = ()
        self._routes: tuple[EnturRoute, ...] = ()
        self._quays: tuple[EnturQuay, ...] = ()
        self._selected_place: EnturStopPlace | None = None
        self._selected_line_whitelist: list[str] = []
        self._selected_route_labels: dict[str, str] = {}
        self._selected_platform_mode = PLATFORM_MODE_STOP_PLACE
        self._selected_quay_ids: list[str] = []
        self._selected_show_on_map = False
        self._existing_line_whitelist: list[str] = []
        self._existing_route_labels: dict[str, str] = {}
        self._existing_stop_id: str | None = None
        self._existing_platform_mode = PLATFORM_MODE_ALL
        self._existing_quay_ids: list[str] = []
        self._existing_show_on_map = False

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
            self._selected_route_labels = dict(user_input.get(CONF_ROUTE_LABELS, {}))
            self._selected_platform_mode = user_input.get(
                CONF_PLATFORM_MODE, PLATFORM_MODE_STOP_PLACE
            )
            self._selected_quay_ids = list(user_input.get(CONF_QUAY_IDS, []))
            self._selected_show_on_map = user_input.get(CONF_SHOW_ON_MAP, False)
            return await self.async_step_confirm()

        return await self._async_step_search("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show the current configuration and choose a maintenance action."""
        self._existing_line_whitelist = list(
            self._get_reconfigure_subentry().data.get(CONF_WHITELIST_LINES, [])
        )
        self._existing_route_labels = dict(
            self._get_reconfigure_subentry().data.get(CONF_ROUTE_LABELS, {})
        )
        self._existing_stop_id = self._get_reconfigure_subentry().data.get(CONF_STOP_ID)
        self._existing_platform_mode = self._get_reconfigure_subentry().data.get(
            CONF_PLATFORM_MODE, PLATFORM_MODE_ALL
        )
        self._existing_quay_ids = list(
            self._get_reconfigure_subentry().data.get(CONF_QUAY_IDS, [])
        )
        self._existing_show_on_map = self._get_reconfigure_subentry().data.get(
            CONF_SHOW_ON_MAP, False
        )
        if user_input is not None:
            if user_input[CONF_RECONFIGURE_ACTION] == RECONFIGURE_ACTION_REPLACE:
                return await self.async_step_replace_stop()
            return await self._async_step_edit_current_stop()

        return self._show_reconfigure_form()

    async def async_step_replace_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Search for a replacement stop place."""
        return await self._async_step_search("replace_stop", user_input)

    async def _async_step_edit_current_stop(self) -> SubentryFlowResult:
        """Load the existing stop place directly for maintenance."""
        if not self._existing_stop_id:
            return self.async_abort(reason="invalid_selection")

        try:
            self._selected_place = await async_get_stop_place(
                self.hass, self._existing_stop_id
            )
        except EnturApiError:
            return self._show_reconfigure_form(errors={"base": "cannot_connect"})

        self._selected_platform_mode = self._existing_platform_mode
        self._selected_quay_ids = self._existing_quay_ids
        self._selected_show_on_map = self._existing_show_on_map
        try:
            self._routes = await async_get_stop_routes(
                self.hass, self._selected_place.stop_id
            )
        except EnturApiError:
            self._routes = ()
        try:
            self._quays = await async_get_stop_quays(
                self.hass, self._selected_place.stop_id
            )
        except EnturApiError:
            self._quays = ()
            if self._existing_platform_mode == PLATFORM_MODE_SELECTED:
                return self._show_reconfigure_form(errors={"base": "cannot_connect"})
        return await self.async_step_select_routes()

    def _show_reconfigure_form(
        self, errors: dict[str, str] | None = None
    ) -> SubentryFlowResult:
        """Show a readable summary of the current stop configuration."""
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_RECONFIGURE_ACTION,
                        default=RECONFIGURE_ACTION_EDIT,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                RECONFIGURE_ACTION_EDIT,
                                RECONFIGURE_ACTION_REPLACE,
                            ],
                            translation_key=CONF_RECONFIGURE_ACTION,
                        )
                    )
                }
            ),
            description_placeholders={
                "name": self._get_reconfigure_subentry().data.get(
                    CONF_STOP_PLACE_NAME,
                    self._get_reconfigure_subentry().title,
                ),
                "routes": _configured_route_summary(
                    self._existing_line_whitelist, self._existing_route_labels
                ),
                "platforms": _configured_platform_summary(
                    self._existing_platform_mode, self._existing_quay_ids
                ),
                "show_on_map": "✓" if self._existing_show_on_map else "—",
            },
            errors=errors or {},
        )

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
                if self._selected_place.stop_id == self._existing_stop_id:
                    self._selected_platform_mode = self._existing_platform_mode
                    self._selected_quay_ids = self._existing_quay_ids
                    self._selected_show_on_map = self._existing_show_on_map
                else:
                    self._selected_platform_mode = PLATFORM_MODE_STOP_PLACE
                    self._selected_quay_ids = []
                    self._selected_show_on_map = False
                try:
                    self._routes = await async_get_stop_routes(
                        self.hass, self._selected_place.stop_id
                    )
                except EnturApiError:
                    self._routes = ()
                try:
                    self._quays = await async_get_stop_quays(
                        self.hass, self._selected_place.stop_id
                    )
                except EnturApiError:
                    self._quays = ()
                return await self.async_step_select_routes()

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
            self._selected_line_whitelist = _combine_line_whitelist(
                user_input.get(CONF_WHITELIST_LINES, []),
                user_input.get(CONF_MANUAL_WHITELIST_LINES, ""),
            )
            self._selected_route_labels = _route_labels(
                self._selected_line_whitelist,
                self._routes,
                (
                    self._existing_route_labels
                    if self._selected_place.stop_id == self._existing_stop_id
                    else None
                ),
            )
            return await self.async_step_select_platforms()

        return self.async_show_form(
            step_id="select_routes",
            data_schema=_route_schema(
                self._routes,
                selected_line_whitelist=(
                    self._existing_line_whitelist
                    if self._selected_place.stop_id == self._existing_stop_id
                    else []
                ),
            ),
        )

    async def async_step_select_platforms(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select the platform detail level for this stop place."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        errors: dict[str, str] = {}
        if user_input is not None:
            mode, quay_ids = _platform_selection(user_input, self._quays)
            if mode == PLATFORM_MODE_SELECTED and not quay_ids:
                errors["base"] = "select_platform"
            else:
                self._selected_platform_mode = mode
                self._selected_quay_ids = quay_ids
                self._selected_show_on_map = user_input.get(CONF_SHOW_ON_MAP, False)
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="select_platforms",
            data_schema=_platform_schema(
                self._quays,
                self._selected_platform_mode,
                self._selected_quay_ids,
                self._selected_show_on_map,
            ),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Confirm the stop place and configure its optional line filter."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        if user_input is not None:
            line_whitelist = self._selected_line_whitelist
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
                CONF_STOP_PLACE_NAME: self._selected_place.name,
                CONF_WHITELIST_LINES: line_whitelist,
                CONF_ROUTE_LABELS: self._selected_route_labels,
                CONF_PLATFORM_MODE: self._selected_platform_mode,
                CONF_QUAY_IDS: self._selected_quay_ids,
                CONF_SHOW_ON_MAP: self._selected_show_on_map,
                CONF_STOP_PLACE_TYPES: list(self._selected_place.stop_place_types),
                CONF_STOP_PLACE_METADATA_VERSION: STOP_PLACE_METADATA_VERSION,
            }
            if self.source == SOURCE_RECONFIGURE:
                _async_reconcile_subentry_entities(
                    self.hass,
                    entry,
                    self._get_reconfigure_subentry(),
                    self._selected_place.stop_id,
                    self._selected_platform_mode,
                    self._selected_quay_ids,
                )
                return self.async_update_and_abort(
                    entry,
                    self._get_reconfigure_subentry(),
                    title=format_stop_place_title(
                        self._selected_place.name,
                        self._selected_place.type_icons,
                        line_whitelist,
                        self._selected_route_labels,
                    ),
                    data=data,
                    unique_id=self._selected_place.stop_id,
                )
            return self.async_create_entry(
                title=format_stop_place_title(
                    self._selected_place.name,
                    self._selected_place.type_icons,
                    line_whitelist,
                    self._selected_route_labels,
                ),
                data=data,
                unique_id=self._selected_place.stop_id,
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=_confirm_schema(),
            description_placeholders=_place_description(self._selected_place),
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
                        _selection_option(place.stop_id, place.selection_label)
                        for place in places
                    ]
                )
            )
        }
    )


def _confirm_schema() -> probatio.Schema:
    """Build the confirmation schema."""
    return probatio.Schema({})


def _place_description(place: EnturStopPlace) -> dict[str, str]:
    """Build confirmation placeholders for a stop place."""
    return {
        "name": place.name,
        "display_name": place.display_name,
        "locality": place.locality or "—",
        "transport_modes": ", ".join(place.transport_modes) or "—",
        "stop_id": place.stop_id,
        "entur_url": place.entur_url,
    }


def _configured_route_summary(line_ids: list[str], route_labels: dict[str, str]) -> str:
    """Return the stored route filter in a readable form."""
    if not line_ids:
        return "—"
    return ", ".join(
        route_labels.get(line_id, line_id_label(line_id)) for line_id in line_ids
    )


def _configured_platform_summary(mode: str, quay_ids: list[str]) -> str:
    """Return the stored platform selection in a readable form."""
    if mode == PLATFORM_MODE_STOP_PLACE:
        return "●"
    if mode == PLATFORM_MODE_SELECTED:
        return str(len(quay_ids))
    return "∞"


def _route_labels(
    line_ids: list[str],
    routes: tuple[EnturRoute, ...],
    existing_labels: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return readable labels for selected API and manually entered lines."""
    labels = existing_labels or {}
    route_labels = {route.line_id: route.selection_label for route in routes}
    return {
        line_id: route_labels.get(line_id, labels.get(line_id, line_id_label(line_id)))
        for line_id in line_ids
    }


@callback
def _async_reconcile_subentry_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    stop_id: str,
    platform_mode: str,
    quay_ids: list[str],
) -> None:
    """Remove registry entries no longer created by a reconfigured stop place."""
    entity_registry = er.async_get(hass)
    old_stop_id = subentry.data.get(CONF_STOP_ID)
    if old_stop_id != stop_id:
        entity_registry.async_clear_config_subentry(
            entry.entry_id, subentry.subentry_id
        )
        dr.async_get(hass).async_clear_config_subentry(
            entry.entry_id, subentry.subentry_id, DOMAIN
        )
        return

    # When all platforms are selected, the set is determined by Entur during setup.
    # Keep the existing platform entries; setup will add the current set after reload.
    if platform_mode == PLATFORM_MODE_ALL:
        return

    expected_unique_ids = (
        set(quay_ids)
        if platform_mode == PLATFORM_MODE_SELECTED and quay_ids
        else {stop_id}
    )
    for registry_entry in entity_registry.entities.get_entries_for_config_entry_id(
        entry.entry_id
    ):
        if (
            registry_entry.config_subentry_id == subentry.subentry_id
            and registry_entry.unique_id not in expected_unique_ids
        ):
            entity_registry.async_remove(registry_entry.entity_id)


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
