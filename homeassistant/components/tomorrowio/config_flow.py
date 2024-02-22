"""Config flow for Tomorrow.io integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pytomorrowio.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
)
from pytomorrowio.pytomorrowio import TomorrowioV4
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.zone import async_active_zone
from homeassistant.const import (
    CONF_API_KEY,
    CONF_FRIENDLY_NAME,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import (
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
    TMRW_ATTR_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)


def _get_config_schema(
    hass: core.HomeAssistant,
    source: str | None,
    input_dict: dict[str, Any] | None = None,
) -> vol.Schema:
    """Return schema defaults for init step based on user input/config dict.

    Retain info already provided for future form views by setting them as
    defaults in schema.
    """
    if input_dict is None:
        input_dict = {}

    api_key_schema = {
        vol.Required(CONF_API_KEY, default=input_dict.get(CONF_API_KEY)): str,
    }

    default_location = input_dict.get(
        CONF_LOCATION,
        {
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
        },
    )
    return vol.Schema(
        {
            **api_key_schema,
            vol.Required(
                CONF_LOCATION,
                default=default_location,
            ): LocationSelector(LocationSelectorConfig(radius=False)),
        },
    )


def _get_unique_id(hass: HomeAssistant, input_dict: dict[str, Any]):
    """Return unique ID from config data."""
    return (
        f"{input_dict[CONF_API_KEY]}"
        f"_{input_dict[CONF_LOCATION][CONF_LATITUDE]}"
        f"_{input_dict[CONF_LOCATION][CONF_LONGITUDE]}"
    )


class TomorrowioOptionsConfigFlow(config_entries.OptionsFlow):
    """Handle Tomorrow.io options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Tomorrow.io options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the Tomorrow.io options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = {
            vol.Required(
                CONF_TIMESTEP,
                default=self._config_entry.options[CONF_TIMESTEP],
            ): vol.In([1, 5, 15, 30, 60]),
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options_schema)
        )


class TomorrowioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tomorrow.io Weather API."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TomorrowioOptionsConfigFlow:
        """Get the options flow for this handler."""
        return TomorrowioOptionsConfigFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                unique_id=_get_unique_id(self.hass, user_input)
            )
            self._abort_if_unique_id_configured()

            location = user_input[CONF_LOCATION]
            latitude = location[CONF_LATITUDE]
            longitude = location[CONF_LONGITUDE]
            if CONF_NAME not in user_input:
                user_input[CONF_NAME] = DEFAULT_NAME
                # Append zone name if it exists and we are using the default name
                if zone_state := async_active_zone(self.hass, latitude, longitude):
                    zone_name = zone_state.attributes[CONF_FRIENDLY_NAME]
                    user_input[CONF_NAME] += f" - {zone_name}"
            try:
                await TomorrowioV4(
                    user_input[CONF_API_KEY],
                    str(latitude),
                    str(longitude),
                    session=async_get_clientsession(self.hass),
                ).realtime([TMRW_ATTR_TEMPERATURE])
            except CantConnectException:
                errors["base"] = "cannot_connect"
            except InvalidAPIKeyException:
                errors[CONF_API_KEY] = "invalid_api_key"
            except RateLimitedException:
                errors[CONF_API_KEY] = "rate_limited"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                options: Mapping[str, Any] = {CONF_TIMESTEP: DEFAULT_TIMESTEP}
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                    options=options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_get_config_schema(self.hass, self.source, user_input),
            errors=errors,
        )
