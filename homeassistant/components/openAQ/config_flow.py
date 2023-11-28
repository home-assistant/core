"""Adds config flow for OpenAQ."""

import openaq
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .aq_client import AQClient
from .const import API_KEY_ID, COUNTRY, DOMAIN, LOCATION, LOCATION_ID

STEP_API_DATA_SCHEMA = vol.Schema({vol.Required(API_KEY_ID): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAQ."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, str] = {}
        self.api_key: str | None = None
        self.country_id: str | None = None
        self.location_id: str | None = None

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle user initiated configuration."""
        errors: dict[str, str] = {}
        countries_dict: dict[str, str] = {}
        locations_dict: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_API_DATA_SCHEMA,
                errors=errors,
            )

        if self.api_key is None:
            self.api_key = user_input[API_KEY_ID]

        if len(countries_dict) == 0:
            countries_dict = get_countries(self.api_key)
            countries = list(countries_dict.keys())

            STEP_COUNTRY_DATA_SCHEMA = vol.Schema(
                {vol.Required(COUNTRY): vol.In(countries)}
            )

        if COUNTRY not in user_input and self.country_id is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_COUNTRY_DATA_SCHEMA, errors=errors
            )

        if self.country_id is None:
            self.country_id = countries_dict[user_input[COUNTRY]]

        if len(locations_dict) == 0:
            locations_dict = get_locations(self.api_key, self.country_id)
            locations = list(locations_dict.keys())

            STEP_LOCATION_DATA_SCHEMA = vol.Schema(
                {vol.Required(LOCATION): vol.In(locations)}
            )

        if LOCATION not in user_input and self.location_id is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_LOCATION_DATA_SCHEMA, errors=errors
            )

        if self.location_id is None:
            self.location_id = locations_dict[user_input[LOCATION]]

        self._data = {API_KEY_ID: self.api_key, LOCATION_ID: self.location_id}

        res = get_device(location_id=self.location_id, api_key=self.api_key).sensors

        name = get_device(location_id=self.location_id, api_key=self.api_key).locality

        if name is None:
            name = {i for i in locations_dict if locations_dict[i] == self.location_id}

        if len(res) == 0:
            errors["location"] = "not_found"
            self.location_id = None
            self.country_id = None
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_COUNTRY_DATA_SCHEMA,
                errors=errors,
            )

        return self.async_create_entry(title=name, data=self._data)


def get_device(location_id, api_key):
    """Return a location."""
    client = AQClient(api_key, location_id, setup_device=False)
    res = client.get_device()
    return res


def get_countries(api_key):
    """Get all the countries available in the API."""
    open_aq_client = openaq.OpenAQ(api_key=api_key)
    countries = open_aq_client.countries
    return {country.name: country.id for country in countries.list().results}


def get_locations(api_key, country_id):
    """Get all the locations available in a country."""
    open_aq_client = openaq.OpenAQ(api_key=api_key)
    locations = open_aq_client.locations
    return {
        location.name: location.id
        for location in locations.list(countries_id=[country_id]).results
    }
