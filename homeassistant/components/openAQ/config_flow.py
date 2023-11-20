"""Adds config flow for OpenAQ."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.openAQ.aq_client import AQClient
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_SENSOR_ID, DOMAIN, SENSOR_ID, COUNTRY_ID, DEFAULT_COUNTRY_ID, API_KEY_ID, CITY_ID, LOCATION_ID


STEP_LOCATION_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(LOCATION_ID): str,
        vol.Required(API_KEY_ID): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAQ."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, str] = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle user initiated configuration."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
            step_id="location", data_schema=STEP_LOCATION_DATA_SCHEMA, errors=errors
        )

        location = get_location(user_input[LOCATION_ID], user_input[API_KEY_ID])
        if location is None:
            errors["location"] = "not_found"
            return self.async_show_form(
            step_id="location", data_schema=STEP_LOCATION_DATA_SCHEMA, errors=errors
        )

        return self.async_create_entry(title="insert location name here", data=user_input)



def get_location(locationid, api_key):
    """Return a location"""
    client = AQClient(api_key, locationid)
    res = client.get_location(locationid)
    return res
