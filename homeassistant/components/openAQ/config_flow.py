"""Adds config flow for OpenAQ."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .aq_client import AQClient
from .const import API_KEY_ID, DOMAIN, LOCATION_ID

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
                step_id="user", data_schema=STEP_LOCATION_DATA_SCHEMA, errors=errors
            )

        self._data = user_input

        res = get_device(
            location_id=user_input[LOCATION_ID], api_key=user_input[API_KEY_ID]
        ).sensors

        name = get_device(
            location_id=user_input[LOCATION_ID], api_key=user_input[API_KEY_ID]
        ).locality

        if len(res) == 0:
            errors["location"] = "not_found"
            return self.async_show_form(
                step_id=self._data[LOCATION_ID],
                data_schema=STEP_LOCATION_DATA_SCHEMA,
                errors=errors,
            )

        return self.async_create_entry(title=name, data=user_input)


def get_device(location_id, api_key):
    """Return a location."""
    client = AQClient(api_key, location_id, setup_device=False)
    res = client.get_device()
    return res
