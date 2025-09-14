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
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import TextSelector

from .const import (
    CONF_DESTINATION,
    CONF_ROUTE,
    CONF_STOP_ID,
    DEFAULT_NAME,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)

_LOGGER = logging.getLogger(__name__)


def _raise_no_data() -> NoReturn:
    """Raise ValueError for no data returned."""
    raise ValueError("No data returned from API")


def _generate_subentry_title(data: dict[str, Any]) -> str:
    """Generate descriptive title for subentry with route/destination context."""
    # Check for custom name first (highest priority)
    custom_name = data.get(CONF_NAME, "").strip()
    if custom_name:
        return custom_name

    stop_id = data[CONF_STOP_ID]
    route = data.get(CONF_ROUTE, "").strip()
    destination = data.get(CONF_DESTINATION, "").strip()

    # Generate contextual title based on available information
    title_parts = [f"Stop {stop_id}"]

    if route and destination:
        title_parts.append(f"({route} → {destination})")
    elif route:
        title_parts.append(f"(Route {route})")
    elif destination:
        title_parts.append(f"(→ {destination})")

    return " ".join(title_parts)


# Main entry schema - API key and optional name
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(),
        vol.Optional(CONF_NAME, default=""): TextSelector(),
    }
)

# Subentry schema - stop details
SUBENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STOP_ID): TextSelector(),
        vol.Optional(CONF_NAME, default=""): TextSelector(),
        vol.Optional(CONF_ROUTE, default=""): TextSelector(),
        vol.Optional(CONF_DESTINATION, default=""): TextSelector(),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_KEY, default=""): TextSelector(),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    api_key = data[CONF_API_KEY]
    custom_name = data.get(CONF_NAME, "").strip()

    # Test the API connection with a dummy stop ID
    transport_nsw = TransportNSW()

    try:
        # Try to get departures with a known valid stop ID to validate the API key
        # Using Central Station stop ID as a test
        await hass.async_add_executor_job(
            transport_nsw.get_departures, "10101100", "", "", api_key
        )

        # We don't care about the result content, just that the API key works
        # Even if this specific stop has no departures, a valid API key should not raise

    except Exception as exc:
        _LOGGER.error("Error connecting to Transport NSW API: %s", exc)
        raise ValueError("Cannot connect to Transport NSW API") from exc

    # Generate entry title
    if custom_name:
        title = custom_name
    else:
        # Generate intelligent default with last 4 characters of API key for uniqueness
        api_suffix = api_key[-4:] if len(api_key) >= 4 else api_key
        title = f"{DEFAULT_NAME} ({api_suffix})"

    return {"title": title}


async def validate_subentry_input(
    hass: HomeAssistant, api_key: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the subentry input allows us to connect.

    Data has the keys from SUBENTRY_SCHEMA with values provided by the user.
    """
    stop_id = data[CONF_STOP_ID]
    route = data.get(CONF_ROUTE, "")
    destination = data.get(CONF_DESTINATION, "")

    # Test the API connection
    transport_nsw = TransportNSW()

    try:
        # Try to get departures to validate the stop ID
        result = await hass.async_add_executor_job(
            transport_nsw.get_departures, stop_id, route, destination, api_key
        )

        # Check if we got a valid response
        if result is None:
            _raise_no_data()

    except Exception as exc:
        _LOGGER.error(
            "Error connecting to Transport NSW API with stop %s: %s", stop_id, exc
        )
        raise ValueError("Cannot connect to Transport NSW API") from exc

    # Generate enhanced title for the subentry
    return {"title": _generate_subentry_title(data)}


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

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported subentry types."""
        return {SUBENTRY_TYPE_STOP: TransportNSWSubentryFlowHandler}


class TransportNSWOptionsFlow(OptionsFlow):
    """Handle Transport NSW options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Check if name or API key was changed
            new_name = user_input.get(CONF_NAME, "").strip()
            current_name = self.config_entry.data.get(CONF_NAME, "").strip()
            new_api_key = user_input.get(CONF_API_KEY, "").strip()
            current_api_key = self.config_entry.data.get(CONF_API_KEY, "").strip()

            updates = {}
            title_update = None

            if new_api_key != current_api_key:
                updates[CONF_API_KEY] = new_api_key

            if new_name != current_name:
                updates[CONF_NAME] = new_name

            # Update title if name changed or if API key changed and no custom name
            if new_name != current_name or (
                new_api_key != current_api_key and not new_name
            ):
                if new_name:
                    title_update = new_name
                else:
                    # Generate default title with API key suffix
                    api_key = (
                        new_api_key
                        if new_api_key != current_api_key
                        else current_api_key
                    )
                    api_suffix = api_key[-4:] if len(api_key) >= 4 else api_key
                    title_update = f"{DEFAULT_NAME} ({api_suffix})"

            result = self.async_create_entry(title="", data=user_input)

            # Update config entry data and title if name was changed
            if updates:
                update_data = {**self.config_entry.data, **updates}
                if title_update:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=update_data, title=title_update
                    )
                else:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=update_data
                    )

            return result

        # Prepare current values for the form
        current_options = dict(self.config_entry.options)
        # Include current values from config entry data
        if (
            CONF_API_KEY not in current_options
            and CONF_API_KEY in self.config_entry.data
        ):
            current_options[CONF_API_KEY] = self.config_entry.data[CONF_API_KEY]
        if CONF_NAME not in current_options and CONF_NAME in self.config_entry.data:
            current_options[CONF_NAME] = self.config_entry.data[CONF_NAME]

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                user_input or current_options,
            ),
        )


class TransportNSWSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding transport stops."""

    def _generate_subentry_unique_id(
        self, parent_entry_id: str, data: dict[str, Any]
    ) -> str:
        """Generate enhanced unique ID for subentry with route/destination context."""
        stop_id = data[CONF_STOP_ID]
        route = data.get(CONF_ROUTE, "").strip()
        destination = data.get(CONF_DESTINATION, "").strip()

        parts = [parent_entry_id, stop_id]

        if route:
            parts.append(f"route_{route}")

        if destination:
            parts.append(f"dest_{destination}")

        return "_".join(parts)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle user step for new subentry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Get the parent entry to access the API key
            parent_entry = self._get_entry()
            api_key = parent_entry.data[CONF_API_KEY]

            try:
                info = await validate_subentry_input(self.hass, api_key, user_input)

                # Generate enhanced unique_id with route and destination context
                unique_id = self._generate_subentry_unique_id(
                    parent_entry.entry_id, user_input
                )

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    unique_id=unique_id,
                )
            except ValueError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-exception-caught
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                SUBENTRY_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of existing subentry."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # Get the parent entry to access the API key
            parent_entry = self._get_entry()
            api_key = parent_entry.data[CONF_API_KEY]

            try:
                info = await validate_subentry_input(self.hass, api_key, user_input)

                return self.async_update_and_abort(
                    parent_entry,
                    subentry,
                    title=info["title"],
                    data_updates=user_input,
                )
            except ValueError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-exception-caught
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Pre-populate form with current subentry data
        current_data = dict(subentry.data)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                SUBENTRY_SCHEMA, user_input or current_data
            ),
            errors=errors,
        )
