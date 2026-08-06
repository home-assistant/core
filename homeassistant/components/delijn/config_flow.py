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
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_ID,
    CONF_STOP_NUMBER,
    DEFAULT_NUMBER_OF_DEPARTURES,
    DOMAIN,
    LOGGER,
)
from .coordinator import DeLijnConfigEntry

CONF_STOP = "stop"
MAX_SEARCH_RESULTS = 10


def _stop_title(stop: Stop) -> str:
    """Return the config entry title for a stop."""
    if stop.municipality:
        return f"{stop.name}, {stop.municipality}"
    return stop.name


def _stop_label(stop: Stop) -> str:
    """Return the select option label for a stop."""
    if stop.municipality:
        return f"{stop.name}, {stop.municipality} ({stop.number})"
    return f"{stop.name} ({stop.number})"


class DeLijnConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for De Lijn."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_key = ""
        self._search_results: list[Stop] = []

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: DeLijnConfigEntry,
    ) -> DeLijnOptionsFlow:
        """Get the options flow for this handler."""
        return DeLijnOptionsFlow()

    async def _async_finish(self, stop: Stop) -> ConfigFlowResult:
        """Create the config entry for the given stop."""
        await self.async_set_unique_id(stop.number)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=_stop_title(stop),
            data={CONF_API_KEY: self._api_key, CONF_STOP_NUMBER: stop.number},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: collect the API key."""
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            return await self.async_step_stop()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
        )

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the stop lookup step: a stop number or a free-text search."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = user_input[CONF_STOP].strip()
            client = DeLijnClient(self._api_key, async_get_clientsession(self.hass))

            if query.isdigit():
                try:
                    stop = await client.get_stop(query)
                except DeLijnNotFoundError:
                    errors["base"] = "invalid_stop"
                except DeLijnAuthError:
                    errors["base"] = "invalid_auth"
                except DeLijnConnectionError:
                    errors["base"] = "cannot_connect"
                except DeLijnError:
                    LOGGER.exception("Unexpected error looking up De Lijn stop")
                    errors["base"] = "unknown"
                else:
                    return await self._async_finish(stop)
            else:
                try:
                    results = await client.search_stops(
                        query, max_results=MAX_SEARCH_RESULTS
                    )
                except DeLijnAuthError:
                    errors["base"] = "invalid_auth"
                except DeLijnConnectionError:
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

        return self.async_show_form(
            step_id="stop",
            data_schema=vol.Schema({vol.Required(CONF_STOP): str}),
            errors=errors,
        )

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle picking a stop from the search results."""
        if user_input is not None:
            selected_number = user_input[CONF_STOP]
            stop = next(
                (s for s in self._search_results if s.number == selected_number),
                None,
            )
            if stop is not None:
                return await self._async_finish(stop)

        options = [
            SelectOptionDict(value=stop.number, label=_stop_label(stop))
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

    @override
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
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            client = DeLijnClient(api_key, async_get_clientsession(self.hass))
            try:
                await client.get_stop(reauth_entry.data[CONF_STOP_NUMBER])
            except DeLijnAuthError:
                errors["base"] = "invalid_auth"
            except DeLijnConnectionError:
                errors["base"] = "cannot_connect"
            except DeLijnError:
                LOGGER.exception("Unexpected error during De Lijn reauthentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates={CONF_API_KEY: api_key}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import of a stop from the legacy YAML sensor platform."""
        api_key = import_data[CONF_API_KEY]
        stop_id = import_data[CONF_STOP_ID]
        client = DeLijnClient(api_key, async_get_clientsession(self.hass))

        try:
            stop = await client.get_stop(stop_id)
        except DeLijnNotFoundError:
            return self.async_abort(reason="invalid_stop")
        except DeLijnAuthError:
            return self.async_abort(reason="invalid_auth")
        except DeLijnConnectionError:
            return self.async_abort(reason="cannot_connect")
        except DeLijnError:
            LOGGER.exception("Unexpected error importing De Lijn stop %s", stop_id)
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(stop.number)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=_stop_title(stop),
            data={CONF_API_KEY: api_key, CONF_STOP_NUMBER: stop.number},
            options={CONF_NUMBER_OF_DEPARTURES: import_data[CONF_NUMBER_OF_DEPARTURES]},
        )


class DeLijnOptionsFlow(OptionsFlowWithReload):
    """Handle De Lijn options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NUMBER_OF_DEPARTURES,
                        default=self.config_entry.options.get(
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
        )
