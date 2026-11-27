"""Config flow for the Fuelprices.dk integration."""

from collections.abc import Mapping
from typing import Any, override

from aiohttp import ClientConnectionError, ClientResponseError
import probatio
from pybraendstofpriser import Braendstofpriser, Flist

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import SERVER_SOFTWARE

from . import FuelpricesDkConfigEntry
from .const import (
    CONF_COMPANY,
    CONF_STATION,
    DOMAIN,
    SUBENTRY_TYPE_STATION,
    WEBSITE_URL,
)


def _get_api_error_key(exc: ClientResponseError) -> str:
    """Map API errors to config flow errors."""
    if exc.status == 401:
        return "invalid_api_key"
    if exc.status == 429:
        return "rate_limit_exceeded"
    return "cannot_connect"


async def _async_fetch_companies(
    api: Braendstofpriser,
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch available fuel companies."""
    try:
        companies = await api.list_companies()
    except ClientResponseError as exc:
        return [], _get_api_error_key(exc)
    except ClientConnectionError, TimeoutError:
        return [], "cannot_connect"

    if not companies:
        return [], "cannot_connect"

    return companies, None


async def _async_fetch_stations(
    api: Braendstofpriser, company_name: str
) -> tuple[Flist[dict[str, Any]], str | None]:
    """Fetch stations for a fuel company."""
    try:
        stations = await api.list_stations(company_name=company_name)
    except ClientResponseError as exc:
        return Flist(), _get_api_error_key(exc)
    except ClientConnectionError, TimeoutError:
        return Flist(), "cannot_connect"

    if not stations:
        return stations, "cannot_connect"

    return stations, None


@callback
def _async_station_is_configured(hass: HomeAssistant, station_id: int) -> bool:
    """Return whether this station is configured under any API key."""
    return any(
        subentry.data[CONF_STATION]["id"] == station_id
        for entry in hass.config_entries.async_entries(DOMAIN, include_ignore=False)
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_STATION)
    )


class FuelpricesDkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fuelprices.dk."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: FuelpricesDkConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {"station": FuelpricesDkStationSubentryFlow}

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api: Braendstofpriser
        self.companies: list[dict[str, Any]] = []
        self.stations: Flist[dict[str, Any]] = Flist()
        self.company_name = ""
        self.user_input: dict[str, Any] = {}

    def _show_company_selection_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Show the company selection form."""
        return self.async_show_form(
            step_id="company_selection",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_COMPANY, default=self.company_name
                    ): probatio.In([c["company"] for c in self.companies]),
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - Enter API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(user_input)
            api = Braendstofpriser(user_input[CONF_API_KEY], user_agent=SERVER_SOFTWARE)
            companies, error = await _async_fetch_companies(api)
            if error is None:
                self.api = api
                self.companies = companies
                self.user_input = dict(user_input)
                return await self.async_step_company_selection()

            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_API_KEY)): str,
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
            self.stations = Flist()
            return await self.async_step_station_selection()

        return self._show_company_selection_form({})

    async def async_step_station_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the station selection step."""
        if not self.stations:
            stations, error = await _async_fetch_stations(self.api, self.company_name)
            if error is not None:
                return self._show_company_selection_form({"base": error})
            self.stations = stations

        if user_input is not None:
            entry_data = {CONF_API_KEY: self.user_input[CONF_API_KEY]}
            self._async_abort_entries_match(entry_data)
            user_input[CONF_STATION] = self.stations.find(
                "name", user_input[CONF_STATION]
            )
            if _async_station_is_configured(self.hass, user_input[CONF_STATION]["id"]):
                return self.async_abort(reason="station_already_configured")

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
                data=entry_data,
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
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_STATION): probatio.In(stations),
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
            api = Braendstofpriser(user_input[CONF_API_KEY], user_agent=SERVER_SOFTWARE)
            _, error = await _async_fetch_companies(api)
            if error is None:
                self._async_abort_entries_match(user_input)
                entry = self._get_reauth_entry()
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
            ),
            errors=errors,
        )


class FuelpricesDkStationSubentryFlow(ConfigSubentryFlow):
    """Handle station subentries for Fuelprices.dk."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.api: Braendstofpriser
        self.companies: list[dict[str, Any]] = []
        self.stations: Flist[dict[str, Any]] = Flist()
        self.company_name = ""
        self.user_input: dict[str, Any] = {}

    def _show_company_selection_form(
        self, errors: dict[str, str] | None = None
    ) -> SubentryFlowResult:
        """Show the company selection form."""
        default_company = self.user_input.get(CONF_COMPANY)
        company_field = (
            probatio.Required(CONF_COMPANY, default=default_company)
            if default_company
            else probatio.Required(CONF_COMPANY)
        )

        return self.async_show_form(
            step_id="company_selection",
            data_schema=probatio.Schema(
                {
                    company_field: probatio.In([c["company"] for c in self.companies]),
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the initial step for adding a station subentry."""
        entry = self._get_entry()
        self.api = Braendstofpriser(
            entry.data[CONF_API_KEY], user_agent=SERVER_SOFTWARE
        )
        self.companies, error = await _async_fetch_companies(self.api)
        if error == "cannot_connect":
            return self.async_show_form(step_id="user", errors={"base": error})
        if error is not None:
            return self.async_abort(reason=error)

        return await self.async_step_company_selection()

    async def async_step_company_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the company selection step."""
        if user_input is not None:
            self.company_name = user_input[CONF_COMPANY]
            self.user_input.update(user_input)
            self.stations = Flist()
            return await self.async_step_station_selection()

        return self._show_company_selection_form()

    async def async_step_station_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the station selection step."""
        if not self.stations:
            stations, error = await _async_fetch_stations(self.api, self.company_name)
            if error is not None:
                self.user_input[CONF_COMPANY] = self.company_name
                return self._show_company_selection_form({"base": error})
            self.stations = stations

        if user_input is not None:
            user_input[CONF_STATION] = self.stations.find(
                "name", user_input[CONF_STATION]
            )

            if _async_station_is_configured(self.hass, user_input[CONF_STATION]["id"]):
                return self.async_abort(reason="station_already_configured")

            self.user_input.update(user_input)
            return await self._async_create_or_update_subentry()

        stations = [s["name"] for s in self.stations]

        return self.async_show_form(
            step_id="station_selection",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_STATION): probatio.In(stations),
                }
            ),
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
