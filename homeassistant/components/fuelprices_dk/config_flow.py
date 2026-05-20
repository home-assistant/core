"""Config flow for the Fuelprices.dk integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientResponseError
from pybraendstofpriser import Braendstofpriser
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

from .const import CONF_COMPANY, CONF_STATION, DOMAIN, WEBSITE_URL


def _get_api_error_key(exc: ClientResponseError) -> str:
    """Map API errors to config flow errors."""
    if exc.status == 401:
        return "invalid_api_key"
    if exc.status == 429:
        return "rate_limit_exceeded"
    return "cannot_connect"


class FuelpricesDkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fuelprices.dk."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {"station": FuelpricesDkStationSubentryFlow}

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api: Braendstofpriser
        self.companies: list[dict[str, Any]] = []
        self.stations: Any = {}
        self.company_name = ""
        self.user_input: dict[str, Any] = {}

    async def _async_validate_api_key(
        self, api_key: str
    ) -> tuple[Braendstofpriser | None, list[dict[str, Any]], str | None]:
        """Validate the API key and fetch available companies."""
        api = Braendstofpriser(api_key)
        try:
            companies = await api.list_companies()
        except ClientResponseError as exc:
            return None, [], _get_api_error_key(exc)

        if not companies:
            return None, [], "cannot_connect"

        return api, companies, None

    async def _async_fetch_stations(self, company_name: str) -> tuple[Any, str | None]:
        """Fetch stations for a company."""
        try:
            stations = await self.api.list_stations(company_name=company_name)
        except ClientResponseError as exc:
            return None, _get_api_error_key(exc)

        if not stations:
            return None, "cannot_connect"

        return stations, None

    def _show_company_selection_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Show the company selection form."""
        return self.async_show_form(
            step_id="company_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COMPANY, default=self.company_name): vol.In(
                        [c["company"] for c in self.companies]
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - Enter API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            api, companies, error = await self._async_validate_api_key(
                user_input[CONF_API_KEY]
            )
            if error is None:
                assert api is not None
                self.api = api
                self.companies = companies
                self.user_input = dict(user_input)
                return await self.async_step_company_selection()

            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
            description_placeholders={"website_url": WEBSITE_URL},
        )

    async def async_step_company_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the company selection step."""
        if user_input is not None:
            self.company_name = user_input[CONF_COMPANY]
            self.user_input.update(user_input)
            self.stations = {}
            return await self.async_step_station_selection()

        return self._show_company_selection_form({})

    async def async_step_station_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the station selection step."""
        if not self.stations:
            stations, error = await self._async_fetch_stations(self.company_name)
            if error is not None:
                return self._show_company_selection_form({"base": error})
            self.stations = stations

        if user_input is not None:
            user_input[CONF_STATION] = self.stations.find(
                "name", user_input[CONF_STATION]
            )

            # Create the main config entry with the first station subentry
            self.user_input.update(user_input)
            unique_id = (
                f"{self.user_input[CONF_COMPANY]}_{self.user_input[CONF_STATION]['id']}"
            )
            title = (
                f"{self.user_input[CONF_COMPANY]} - "
                f"{self.user_input[CONF_STATION]['name']}"
            )
            return self.async_create_entry(
                title="Fuelprices.dk",
                data={CONF_API_KEY: self.user_input[CONF_API_KEY]},
                subentries=[
                    {
                        "subentry_type": "station",
                        "data": {
                            CONF_COMPANY: self.user_input[CONF_COMPANY],
                            CONF_STATION: self.user_input[CONF_STATION],
                        },
                        "title": title,
                        "unique_id": unique_id,
                    }
                ],
            )

        stations = [s["name"] for s in self.stations]

        return self.async_show_form(
            step_id="station_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION): vol.In(stations),
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauth flow when API key is invalid/expired."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a new API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = Braendstofpriser(user_input[CONF_API_KEY])
            try:
                await api.list_companies()
            except ClientResponseError as exc:
                errors["base"] = _get_api_error_key(exc)

            if not errors:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                if entry is not None:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={CONF_API_KEY: user_input[CONF_API_KEY]},
                    )
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )


class FuelpricesDkStationSubentryFlow(ConfigSubentryFlow):
    """Handle station subentries for Fuelprices.dk."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.api: Braendstofpriser
        self.companies: list[dict[str, Any]] = []
        self.stations: Any = {}
        self.company_name = ""
        self._errors: dict[str, str] = {}
        self.user_input: dict[str, Any] = {}

    async def _async_fetch_stations(self, company_name: str) -> tuple[Any, str | None]:
        """Fetch stations for a company."""
        try:
            stations = await self.api.list_stations(company_name=company_name)
        except ClientResponseError as exc:
            return None, _get_api_error_key(exc)

        if not stations:
            return None, "cannot_connect"

        return stations, None

    def _show_company_selection_form(
        self, errors: dict[str, str] | None = None
    ) -> SubentryFlowResult:
        """Show the company selection form."""
        default_company = self.user_input.get(CONF_COMPANY)
        company_field = (
            vol.Required(CONF_COMPANY, default=default_company)
            if default_company
            else vol.Required(CONF_COMPANY)
        )

        return self.async_show_form(
            step_id="company_selection",
            data_schema=vol.Schema(
                {
                    company_field: vol.In([c["company"] for c in self.companies]),
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the initial step for adding a station subentry."""
        await self._async_init_api()
        return await self.async_step_company_selection(user_input)

    async def _async_init_api(self) -> None:
        """Initialize API client and fetch companies."""
        entry = self._get_entry()
        api_key = entry.data[CONF_API_KEY]
        self.api = Braendstofpriser(api_key)
        try:
            self.companies = await self.api.list_companies()
        except ClientResponseError as exc:
            self._errors["base"] = _get_api_error_key(exc)
            return

        if not self.companies:
            self._errors["base"] = "cannot_connect"

    async def async_step_company_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the company selection step."""
        if self._errors:
            return self.async_abort(reason=self._errors["base"])

        if user_input is not None:
            self.company_name = user_input[CONF_COMPANY]
            self.user_input.update(user_input)
            self.stations = {}
            return await self.async_step_station_selection()

        return self._show_company_selection_form()

    async def async_step_station_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the station selection step."""
        if not self.stations:
            stations, error = await self._async_fetch_stations(self.company_name)
            if error is not None:
                self.user_input[CONF_COMPANY] = self.company_name
                return self._show_company_selection_form({"base": error})
            self.stations = stations

        if user_input is not None:
            user_input[CONF_STATION] = self.stations.find(
                "name", user_input[CONF_STATION]
            )

            # Set UniqueID and abort if already existing
            unique_id = (
                f"{self.user_input[CONF_COMPANY]}_{user_input[CONF_STATION]['id']}"
            )
            entry = self._get_entry()
            for subentry in entry.subentries.values():
                if subentry.unique_id == unique_id:
                    return self.async_abort(reason="station_already_configured")

            # Process the user input and show next selection form
            self.user_input.update(user_input)
            return await self._async_create_or_update_subentry()

        stations = [s["name"] for s in self.stations]

        return self.async_show_form(
            step_id="station_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION): vol.In(stations),
                }
            ),
            errors=self._errors,
        )

    async def _async_create_or_update_subentry(self) -> SubentryFlowResult:
        """Create the station subentry."""
        subentry_data = {
            CONF_COMPANY: self.user_input[CONF_COMPANY],
            CONF_STATION: self.user_input[CONF_STATION],
        }
        unique_id = (
            f"{self.user_input[CONF_COMPANY]}_{self.user_input[CONF_STATION]['id']}"
        )
        title = (
            f"{self.user_input[CONF_COMPANY]} - {self.user_input[CONF_STATION]['name']}"
        )

        entry = self._get_entry()
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(
            title=title,
            data=subentry_data,
            unique_id=unique_id,
        )
