"""Config flow for the Entur public transport integration."""

from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .api import EnturApiError, EnturStopPlace, async_search_stop_places
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
)


class EnturConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entur public transport."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._places: tuple[EnturStopPlace, ...] = ()
        self._selected_place: EnturStopPlace | None = None

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
    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the selected stop place before creating the entry."""
        if self._selected_place is None:
            return self.async_abort(reason="invalid_selection")

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_STOP_IDS: [self._selected_place.stop_id]}
            )
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data=_entry_data([self._selected_place.stop_id]),
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={
                "name": self._selected_place.name,
                "display_name": self._selected_place.display_name,
                "locality": self._selected_place.locality or "Unknown",
                "transport_modes": ", ".join(self._selected_place.transport_modes)
                or "Unknown",
                "stop_id": self._selected_place.stop_id,
                "role": (
                    "transport hub"
                    if self._selected_place.role == "parent"
                    else "standalone stop place"
                ),
                "entur_url": self._selected_place.entur_url,
            },
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
