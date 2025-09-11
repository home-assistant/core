"""Config flow for Transport NSW integration."""

from __future__ import annotations

import logging
from typing import Any, NoReturn

from TransportNSW import TransportNSW
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import TextSelector

from .const import CONF_DESTINATION, CONF_ROUTE, CONF_STOP_ID, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _raise_no_data() -> NoReturn:
    """Raise ValueError for no data returned."""
    raise ValueError("No data returned from API")


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(),
        vol.Required(CONF_STOP_ID): TextSelector(),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Optional(CONF_ROUTE, default=""): TextSelector(),
        vol.Optional(CONF_DESTINATION, default=""): TextSelector(),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Optional(CONF_ROUTE, default=""): TextSelector(),
        vol.Optional(CONF_DESTINATION, default=""): TextSelector(),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    api_key = data[CONF_API_KEY]
    stop_id = data[CONF_STOP_ID]

    # Test the API connection
    transport_nsw = TransportNSW()

    try:
        # Try to get departures to validate the API key and stop ID
        result = await hass.async_add_executor_job(
            transport_nsw.get_departures, stop_id, "", "", api_key
        )

        # Check if we got a valid response
        if result is None:
            _raise_no_data()

    except Exception as exc:
        _LOGGER.error("Error connecting to Transport NSW API: %s", exc)
        raise ValueError("Cannot connect to Transport NSW API") from exc

    # Return info that you want to store in the config entry.
    return {"title": f"{data[CONF_NAME]} ({stop_id})"}


class TransportNSWConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Transport NSW."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ValueError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-exception-caught
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(DATA_SCHEMA, user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TransportNSWOptionsFlow:
        """Get the options flow for this handler."""
        return TransportNSWOptionsFlow(config_entry)


class TransportNSWOptionsFlow(OptionsFlow):
    """Handle Transport NSW options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # If name was changed, update the config entry data as well
            updates = {}
            if CONF_NAME in user_input and user_input[
                CONF_NAME
            ] != self.config_entry.data.get(CONF_NAME):
                updates[CONF_NAME] = user_input[CONF_NAME]

            result = self.async_create_entry(title="", data=user_input)

            # Update config entry data if name was changed
            if updates:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, **updates}
                )

            return result

        # Prepare current values for the form
        current_options = dict(self.config_entry.options)
        # Include current name from config entry data
        if CONF_NAME not in current_options and CONF_NAME in self.config_entry.data:
            current_options[CONF_NAME] = self.config_entry.data[CONF_NAME]

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                user_input or current_options,
            ),
        )
