"""Config flow for Tomorrow.io integration."""
from __future__ import annotations

import logging
from typing import Any, Mapping

from pytomorrowio.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
)
from pytomorrowio.pytomorrowio import TomorrowioV4
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.components.climacell.const import DOMAIN as CC_DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CC_ATTR_TEMPERATURE,
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
    INTEGRATION_NAME,
)

_LOGGER = logging.getLogger(__name__)


def _get_config_schema(
    hass: core.HomeAssistant, input_dict: dict[str, Any] = None
) -> vol.Schema:
    """
    Return schema defaults for init step based on user input/config dict.

    Retain info already provided for future form views by setting them as
    defaults in schema.
    """
    if input_dict is None:
        input_dict = {}

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=input_dict.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            vol.Required(CONF_API_KEY, default=input_dict.get(CONF_API_KEY)): str,
            vol.Required(
                CONF_LATITUDE,
                "location",
                default=input_dict.get(CONF_LATITUDE, hass.config.latitude),
            ): cv.latitude,
            vol.Required(
                CONF_LONGITUDE,
                "location",
                default=input_dict.get(CONF_LONGITUDE, hass.config.longitude),
            ): cv.longitude,
        },
        extra=vol.REMOVE_EXTRA,
    )


def _get_unique_id(hass: HomeAssistant, input_dict: dict[str, Any]):
    """Return unique ID from config data."""
    return (
        f"{input_dict[CONF_API_KEY]}"
        f"_{input_dict.get(CONF_LATITUDE, hass.config.latitude)}"
        f"_{input_dict.get(CONF_LONGITUDE, hass.config.longitude)}"
    )


class TomorrowioOptionsConfigFlow(config_entries.OptionsFlow):
    """Handle Tomorrow.io options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Tomorrow.io options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Manage the Tomorrow.io options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = {
            vol.Required(
                CONF_TIMESTEP,
                default=self._config_entry.options.get(CONF_TIMESTEP, DEFAULT_TIMESTEP),
            ): vol.In([1, 5, 15, 30]),
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options_schema)
        )


class TomorrowioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tomorrow.io Weather API."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._showed_import_message = False
        self._import_config: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TomorrowioOptionsConfigFlow:
        """Get the options flow for this handler."""
        return TomorrowioOptionsConfigFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None or (user_input := self._import_config):
            await self.async_set_unique_id(
                unique_id=_get_unique_id(self.hass, user_input)
            )
            self._abort_if_unique_id_configured()

            try:
                await TomorrowioV4(
                    user_input[CONF_API_KEY],
                    str(user_input.get(CONF_LATITUDE, self.hass.config.latitude)),
                    str(user_input.get(CONF_LONGITUDE, self.hass.config.longitude)),
                    session=async_get_clientsession(self.hass),
                ).realtime([CC_ATTR_TEMPERATURE])

                options: Mapping[str, Any] = {}
                # Store the old config entry ID and retrieve options to recreate the entry
                if self.source == config_entries.SOURCE_IMPORT:
                    old_config_entry_id = self.context["old_config_entry_id"]
                    old_config_entry = self.hass.config_entries.async_get_entry(
                        old_config_entry_id
                    )
                    assert old_config_entry
                    options = old_config_entry.options
                    user_input["old_config_entry_id"] = old_config_entry_id
                    self.hass.components.persistent_notification.async_dismiss(
                        self.hass, f"{CC_DOMAIN}_to_{DOMAIN}_new_api_key_needed"
                    )

                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input, options=options
                )
            except CantConnectException:
                errors["base"] = "cannot_connect"
            except InvalidAPIKeyException:
                errors[CONF_API_KEY] = "invalid_api_key"
            except RateLimitedException:
                errors[CONF_API_KEY] = "rate_limited"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=_get_config_schema(self.hass, user_input),
            errors=errors,
        )

    async def async_step_upgrade_needed(self, import_config: dict = None) -> FlowResult:
        """Tell the user upgrade is needed and what will happen after config flow."""
        if not self._showed_import_message:
            self._showed_import_message = True
            return self.async_show_form(step_id="upgrade_needed")

        return await self.async_step_user()

    async def async_step_import(self, import_config: dict) -> FlowResult:
        """Import from config."""
        # Store import config for later
        self._import_config = dict(import_config)
        if self._import_config.pop(CONF_API_VERSION, 3) == 3:
            # Clear API key from import config
            self._import_config[CONF_API_KEY] = ""
            self.hass.components.persistent_notification.async_create(
                self.hass,
                (
                    "As part of [ClimaCell's rebranding to Tomorrow.io](https://www.tomorrow.io/blog/my-last-day-as-ceo-of-climacell/) "
                    "we will migrate your existing ClimaCell config entry (or config "
                    "entries) to the new Tomorrow.io integration, but in order to "
                    "complete this activity, we will need your input. Visit the "
                    "[Integrations Configuration](/config/integrations) page and "
                    "click Configure on the Tomorrow.io card(s) to learn more."
                ),
                INTEGRATION_NAME,
                f"{CC_DOMAIN}_to_{DOMAIN}_new_api_key_needed",
            )
            return await self.async_step_upgrade_needed()

        self.hass.components.persistent_notification.async_create(
            self.hass,
            (
                "As part of [ClimaCell's rebranding to Tomorrow.io](https://www.tomorrow.io/blog/my-last-day-as-ceo-of-climacell/) "
                "we have automatically migrated your existing ClimaCell config entry "
                "(or as many of your ClimaCell config entries as we could) to the new "
                "Tomorrow.io integration. There is nothing you need to do since the "
                "new integration is a drop in replacement and your existing entities "
                "have been migrated over, just note that the location of the "
                "integration card on the "
                "[Integrations Configuration](/config/integrations) page has changed "
                "since the integration name has changed."
            ),
            INTEGRATION_NAME,
            f"{CC_DOMAIN}_to_{DOMAIN}",
        )
        return await self.async_step_user(self._import_config)
