"""Config flow for the De Lijn integration."""

from collections.abc import Mapping
from typing import Any, override

from pydelijn import (
    DeLijnAuthError,
    DeLijnClient,
    DeLijnConnectionError,
    DeLijnError,
    DeLijnNotFoundError,
    Stop,
)
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_STOP,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_NUMBER,
    CONF_SUBENTRIES,
    DEFAULT_NUMBER_OF_DEPARTURES,
    DOMAIN,
    LOGGER,
    SUBENTRY_TYPE_STOP,
)
from .util import stop_delijn_url, stop_label, stop_map_url, stop_title

MAX_SEARCH_RESULTS = 10
PREVIEW_PASSAGES = 3


class DeLijnConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for De Lijn: the account (API key) only."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _async_validate_api_key(self, api_key: str) -> dict[str, str]:
        """Validate an API key with a cheap call. Returns a dict of errors."""
        client = DeLijnClient(api_key, async_get_clientsession(self.hass))
        try:
            await client.get_stops_near(
                self.hass.config.latitude, self.hass.config.longitude, max_results=1
            )
        except DeLijnAuthError:
            return {"base": "invalid_auth"}
        except DeLijnConnectionError:
            return {"base": "cannot_connect"}
        except DeLijnError:
            LOGGER.exception("Unexpected error validating the De Lijn API key")
            return {"base": "unknown"}
        return {}

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_STOP: StopSubentryFlowHandler}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: collect and validate the API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            self._async_abort_entries_match({CONF_API_KEY: api_key})
            errors = await self._async_validate_api_key(api_key)
            if not errors:
                return self.async_create_entry(
                    title="De Lijn", data={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle changing the API key on the main entry."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            self._async_abort_entries_match({CONF_API_KEY: api_key})
            errors = await self._async_validate_api_key(api_key)
            if not errors:
                return self.async_update_and_abort(
                    reconfigure_entry, data_updates={CONF_API_KEY: api_key}
                )

        schema = self.add_suggested_values_to_schema(
            vol.Schema({vol.Required(CONF_API_KEY): str}),
            {CONF_API_KEY: reconfigure_entry.data[CONF_API_KEY]},
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication with a new API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            self._async_abort_entries_match({CONF_API_KEY: api_key})
            errors = await self._async_validate_api_key(api_key)
            if not errors:
                return self.async_update_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Create the main entry together with its stops during YAML import.

        The sensor platform's import handler has already validated every
        stop; creating them as subentries here, atomically with the entry,
        means the entry is only ever set up once with its full final state.
        """
        api_key = import_data[CONF_API_KEY]
        self._async_abort_entries_match({CONF_API_KEY: api_key})
        return self.async_create_entry(
            title="De Lijn",
            data={CONF_API_KEY: api_key},
            subentries=import_data[CONF_SUBENTRIES],
        )


class StopSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding, and reconfiguring, a De Lijn stop."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self._search_results: list[Stop] = []
        self._pending_stop: Stop | None = None

    @property
    def _api_key(self) -> str:
        """Return the API key of the parent config entry."""
        return self._get_entry().data[CONF_API_KEY]

    def _is_stop_configured(self, stop_number: str) -> bool:
        """Return whether the stop is already configured on any De Lijn entry.

        Sensor unique ids are scoped to the stop number only, so the same
        stop configured on two entries would collide; it must be rejected
        as a duplicate no matter which account already has it.
        """
        return any(
            subentry.unique_id == stop_number
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            for subentry in entry.subentries.values()
        )

    async def _async_finish(self, stop: Stop) -> SubentryFlowResult:
        """Create the subentry for the given stop."""
        if self._is_stop_configured(stop.number):
            return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title=stop_title(stop),
            data={
                CONF_STOP_NUMBER: stop.number,
                CONF_NUMBER_OF_DEPARTURES: DEFAULT_NUMBER_OF_DEPARTURES,
            },
            unique_id=stop.number,
        )

    async def _async_departure_preview(self, stop: Stop) -> str:
        """Return a short preview of the next few departures for a stop.

        Returns an empty string if there is nothing to show (no upcoming
        departures, or the preview could not be loaded); the confirm step's
        description already explains that case to the user.
        """
        client = DeLijnClient(self._api_key, async_get_clientsession(self.hass))
        try:
            passages = await client.get_passages(
                stop.number, max_passages=PREVIEW_PASSAGES
            )
        except DeLijnError:
            LOGGER.exception("Unexpected error loading a De Lijn departure preview")
            return ""

        if not passages:
            return ""

        lines = []
        for passage in passages:
            line_number = passage.line.public_number or passage.line.number
            due_at = (
                dt_util.as_local(passage.due_at).strftime("%H:%M")
                if passage.due_at
                else "?"
            )
            destination = passage.destination or "?"
            lines.append(f"{line_number} → {destination} ({due_at})")
        return "\n".join(lines)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the stop lookup step.

        A stop number or free-text search takes priority; otherwise a
        location picked on the map is used, falling back to the Home
        Assistant location if both are left empty.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            self._search_results = []
            query = (user_input.get(CONF_STOP) or "").strip()
            client = DeLijnClient(self._api_key, async_get_clientsession(self.hass))

            if query:
                if query.isdigit():
                    try:
                        stop = await client.get_stop(query)
                    except DeLijnNotFoundError:
                        errors["base"] = "invalid_stop"
                    except DeLijnAuthError as err:
                        LOGGER.error(
                            "De Lijn rejected the API key while looking up a stop: %s",
                            err,
                        )
                        errors["base"] = "invalid_auth"
                    except DeLijnConnectionError as err:
                        LOGGER.error(
                            "Error connecting to the De Lijn API while looking up a"
                            " stop: %s",
                            err,
                        )
                        errors["base"] = "cannot_connect"
                    except DeLijnError:
                        LOGGER.exception("Unexpected error looking up De Lijn stop")
                        errors["base"] = "unknown"
                    else:
                        self._pending_stop = stop
                        return await self.async_step_confirm()
                else:
                    try:
                        results = await client.search_stops(
                            query, max_results=MAX_SEARCH_RESULTS
                        )
                    except DeLijnAuthError as err:
                        LOGGER.error(
                            "De Lijn rejected the API key while searching for"
                            " stops: %s",
                            err,
                        )
                        errors["base"] = "invalid_auth"
                    except DeLijnConnectionError as err:
                        LOGGER.error(
                            "Error connecting to the De Lijn API while searching for"
                            " stops: %s",
                            err,
                        )
                        errors["base"] = "cannot_connect"
                    except DeLijnError:
                        LOGGER.exception("Unexpected error searching De Lijn stops")
                        errors["base"] = "unknown"
                    else:
                        if not results:
                            errors["base"] = "no_results"
                        else:
                            self._search_results = results
                            return await self.async_step_pick()
            else:
                if (location := user_input.get(CONF_LOCATION)) is not None:
                    latitude = location[CONF_LATITUDE]
                    longitude = location[CONF_LONGITUDE]
                else:
                    latitude = self.hass.config.latitude
                    longitude = self.hass.config.longitude

                try:
                    results = await client.get_stops_near(
                        latitude, longitude, max_results=MAX_SEARCH_RESULTS
                    )
                except DeLijnAuthError as err:
                    LOGGER.error(
                        "De Lijn rejected the API key while finding nearby stops: %s",
                        err,
                    )
                    errors["base"] = "invalid_auth"
                except DeLijnConnectionError as err:
                    LOGGER.error(
                        "Error connecting to the De Lijn API while finding nearby"
                        " stops: %s",
                        err,
                    )
                    errors["base"] = "cannot_connect"
                except DeLijnError:
                    LOGGER.exception("Unexpected error finding nearby De Lijn stops")
                    errors["base"] = "unknown"
                else:
                    if not results:
                        errors["base"] = "no_results"
                    else:
                        self._search_results = results
                        return await self.async_step_pick()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_STOP): str,
                    vol.Optional(CONF_LOCATION): LocationSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle picking a stop from the search results."""
        if user_input is not None:
            selected_number = user_input[CONF_STOP]
            stop = next(
                (s for s in self._search_results if s.number == selected_number),
                None,
            )
            if stop is not None:
                self._pending_stop = stop
                return await self.async_step_confirm()

        options = [
            SelectOptionDict(value=stop.number, label=stop_label(stop))
            for stop in self._search_results
        ]
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show a departure preview so the user can confirm the right stop."""
        stop = self._pending_stop
        assert stop is not None

        menu_options = (
            ["create_entry"] + (["pick"] if self._search_results else []) + ["user"]
        )
        return self.async_show_menu(
            step_id="confirm",
            menu_options=menu_options,
            description_placeholders={
                "name": stop.name,
                "municipality": f", {stop.municipality}" if stop.municipality else "",
                "number": stop.number,
                "departures": await self._async_departure_preview(stop),
                "delijn_url": stop_delijn_url(stop.number),
                "map_url": stop_map_url(stop),
            },
        )

    async def async_step_create_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create the subentry for the stop confirmed in the menu step."""
        stop = self._pending_stop
        assert stop is not None
        return await self._async_finish(stop)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle changing the number of departures for an existing stop."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(), subentry, data_updates=user_input
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NUMBER_OF_DEPARTURES,
                        default=subentry.data.get(
                            CONF_NUMBER_OF_DEPARTURES, DEFAULT_NUMBER_OF_DEPARTURES
                        ),
                    ): vol.All(
                        NumberSelector(
                            NumberSelectorConfig(
                                min=1, max=20, mode=NumberSelectorMode.BOX
                            )
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
            description_placeholders={
                "stop_number": subentry.data[CONF_STOP_NUMBER],
            },
        )
