"""Config flow for dk_fuelprices integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientResponseError
from pybraendstofpriser import Braendstofpriser
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback

from .const import CONF_COMPANY, CONF_PRODUCTS, CONF_STATION, DOMAIN, WEBSITE_URL

_LOGGER = logging.getLogger(__name__)


class BraendstofpriserConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dk_fuelprices."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {"station": BraendstofpriserStationSubentryFlow}

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api: Braendstofpriser
        self.companies: list[dict[str, Any]] = []
        self.stations: Any = {}
        self.company_name = ""
        self._errors: dict[str, str] = {}
        self.user_input: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step - Enter API key."""
        self._async_abort_entries_match()
        if user_input is not None:
            # Test API key
            try:
                # Initialize API
                self.api = Braendstofpriser(user_input[CONF_API_KEY])
                self.companies = await self.api.list_companies()
            except ClientResponseError as exc:  # pylint: disable=broad-except
                if exc.status == 401:
                    self._errors["base"] = "invalid_api_key"
                    return self.async_abort(reason="invalid_api_key")
                if exc.status == 429:
                    self._errors["base"] = "rate_limit_exceeded"
                    return self.async_abort(reason="rate_limit_exceeded")
                self._errors["base"] = "cannot_connect"
                return self.async_abort(reason="cannot_connect")

            # Proceed to company selection
            self.user_input.update(user_input)
            return await self.async_step_company_selection()

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=self._errors,
            description_placeholders={"website_url": WEBSITE_URL},
        )

    async def async_step_company_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the company selection step."""
        if user_input is not None:
            # Process the user input and show next selection form
            self.company_name = user_input[CONF_COMPANY]
            self.user_input.update(user_input)
            return await self.async_step_station_selection()

        if len(self.companies) == 0:
            return self.async_abort(reason="rate_limit_exceeded")

        # Show the form to the user
        return self.async_show_form(
            step_id="company_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COMPANY): vol.In(
                        [c["company"] for c in self.companies]
                    ),
                }
            ),
            errors=self._errors,
        )

    async def async_step_station_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the station selection step."""
        if user_input is not None:
            # Match station name to station ID
            user_input[CONF_STATION] = self.stations.find(
                "name", user_input[CONF_STATION]
            )

            # Process the user input and show next selection form
            self.user_input.update(user_input)
            return await self.async_step_product_selection()

        # Get station list, sort it and make a list with only names
        self.stations = await self.api.list_stations(company_name=self.company_name)
        stations = [s["name"] for s in self.stations]

        # Show the form to the user
        return self.async_show_form(
            step_id="station_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION): vol.In(stations),
                }
            ),
            errors=self._errors,
        )

    async def async_step_product_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the product selection step."""
        if user_input is not None:
            # Create the main config entry and store first subentry data
            return self.async_create_entry(
                title="Fuelprices.dk",
                data={
                    CONF_API_KEY: self.user_input[CONF_API_KEY],
                    CONF_COMPANY: self.user_input[CONF_COMPANY],
                    CONF_STATION: self.user_input[CONF_STATION],
                    CONF_PRODUCTS: user_input,
                },
            )

        try:
            # Get available products and translate the system names to human readable
            products_available = await self.api.get_prices(
                self.user_input[CONF_STATION]["id"]
            )
        except ClientResponseError as exc:  # pylint: disable=broad-except
            if exc.status == 429:
                self._errors["base"] = "rate_limit_exceeded"
                return self.async_abort(reason="rate_limit_exceeded")
            self._errors["base"] = "cannot_connect"
            return self.async_abort(reason="cannot_connect")

        # Create a list of available products
        schema = {}
        for prod in products_available["prices"]:
            schema.update({vol.Required(prod): bool})

        # Show the form to the user
        return self.async_show_form(
            step_id="product_selection",
            data_schema=vol.Schema(schema),
            errors=self._errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle a reauth flow when API key is invalid/expired."""
        self._errors = {}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm a new API key."""
        if user_input is not None:
            try:
                api = Braendstofpriser(user_input[CONF_API_KEY])
                await api.list_companies()
            except ClientResponseError as exc:  # pylint: disable=broad-except
                if exc.status == 401:
                    self._errors["base"] = "invalid_api_key"
                elif exc.status == 429:
                    self._errors["base"] = "rate_limit_exceeded"
                else:
                    self._errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="reauth_confirm",
                    data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
                    errors=self._errors,
                )

            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
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
            errors=self._errors,
        )


class BraendstofpriserStationSubentryFlow(config_entries.ConfigSubentryFlow):
    """Handle station subentries for dk_fuelprices."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.api: Braendstofpriser
        self.companies: list[dict[str, Any]] = []
        self.stations: Any = {}
        self.company_name = ""
        self._errors: dict[str, str] = {}
        self.user_input: dict[str, Any] = {}
        self._reconfigure = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Handle the initial step for adding a station subentry."""
        await self._async_init_api()
        return await self.async_step_company_selection(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Handle reconfiguring an existing station subentry."""
        self._reconfigure = True
        subentry = self._get_reconfigure_subentry()
        self.user_input = dict(subentry.data)
        await self._async_init_api()
        return await self.async_step_product_selection(user_input)

    async def _async_init_api(self) -> None:
        """Initialize API client and fetch companies."""
        entry = self._get_entry()
        api_key = entry.data.get(CONF_API_KEY)
        if not api_key:
            self._errors["base"] = "invalid_api_key"
            return

        try:
            self.api = Braendstofpriser(api_key)
            self.companies = await self.api.list_companies()
        except ClientResponseError as exc:  # pylint: disable=broad-except
            if exc.status == 401:
                self._errors["base"] = "invalid_api_key"
            elif exc.status == 429:
                self._errors["base"] = "rate_limit_exceeded"
            else:
                self._errors["base"] = "cannot_connect"

    async def async_step_company_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Handle the company selection step."""
        if self._errors:
            return self.async_abort(reason=self._errors["base"])

        if user_input is not None:
            # Process the user input and show next selection form
            self.company_name = user_input[CONF_COMPANY]
            self.user_input.update(user_input)
            return await self.async_step_station_selection()

        if len(self.companies) == 0:
            return self.async_abort(reason="rate_limit_exceeded")

        default_company = self.user_input.get(CONF_COMPANY)
        company_field = (
            vol.Required(CONF_COMPANY, default=default_company)
            if default_company
            else vol.Required(CONF_COMPANY)
        )

        # Show the form to the user
        return self.async_show_form(
            step_id="company_selection",
            data_schema=vol.Schema(
                {
                    company_field: vol.In([c["company"] for c in self.companies]),
                }
            ),
            errors=self._errors,
        )

    async def async_step_station_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Handle the station selection step."""
        if user_input is not None:
            # Match station name to station ID
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
                    if not self._reconfigure or (
                        subentry.subentry_id != self._reconfigure_subentry_id
                    ):
                        return self.async_abort(reason="already_configured")

            # Process the user input and show next selection form
            self.user_input.update(user_input)
            return await self.async_step_product_selection()

        # Get station list, sort it and make a list with only names
        self.stations = await self.api.list_stations(company_name=self.company_name)
        stations = [s["name"] for s in self.stations]

        default_station_name = None
        if self._reconfigure and self.user_input.get(CONF_STATION):
            default_station_name = self.user_input[CONF_STATION].get("name")

        station_field = (
            vol.Required(CONF_STATION, default=default_station_name)
            if default_station_name
            else vol.Required(CONF_STATION)
        )

        # Show the form to the user
        return self.async_show_form(
            step_id="station_selection",
            data_schema=vol.Schema(
                {
                    station_field: vol.In(stations),
                }
            ),
            errors=self._errors,
        )

    async def async_step_product_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Handle the product selection step."""
        if user_input is not None:
            # Process the user input and create/update the subentry
            subentry_data = {
                CONF_COMPANY: self.user_input[CONF_COMPANY],
                CONF_STATION: self.user_input[CONF_STATION],
                CONF_PRODUCTS: user_input,
            }
            unique_id = (
                f"{self.user_input[CONF_COMPANY]}_{self.user_input[CONF_STATION]['id']}"
            )
            title = (
                f"{self.user_input[CONF_COMPANY]} - "
                f"{self.user_input[CONF_STATION]['name']}"
            )

            if self._reconfigure:
                entry = self._get_entry()
                subentry = self._get_reconfigure_subentry()
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_update_and_abort(
                    entry,
                    subentry,
                    data=subentry_data,
                    title=title,
                    unique_id=unique_id,
                )

            entry = self._get_entry()
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(
                title=title,
                data=subentry_data,
                unique_id=unique_id,
            )

        try:
            # Get available products and translate the system names to human readable
            products_available = await self.api.get_prices(
                self.user_input[CONF_STATION]["id"]
            )
        except ClientResponseError as exc:  # pylint: disable=broad-except
            if exc.status == 429:
                self._errors["base"] = "rate_limit_exceeded"
                return self.async_abort(reason="rate_limit_exceeded")
            self._errors["base"] = "cannot_connect"
            return self.async_abort(reason="cannot_connect")

        product_options = self.user_input.get(CONF_PRODUCTS, {})

        # Create a list of available products
        schema = {}
        for prod in products_available["prices"]:
            schema.update(
                {vol.Required(prod, default=product_options.get(prod, False)): bool}
            )

        # Show the form to the user
        return self.async_show_form(
            step_id="product_selection",
            data_schema=vol.Schema(schema),
            errors=self._errors,
        )
