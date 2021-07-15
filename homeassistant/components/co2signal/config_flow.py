"""Config flow for Co2signal integration."""
from __future__ import annotations

import logging
from typing import Any

import CO2Signal
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_TOKEN,
)
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_COUNTRY_CODE, DOMAIN, HOME_LOCATION_NAME, MSG_LOCATION

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Co2signal."""

    VERSION = 1

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        import_info[CONF_API_KEY] = import_info.pop(CONF_TOKEN)
        if import_info.get(CONF_COUNTRY_CODE) is None:
            import_info[CONF_LATITUDE] = import_info.get(
                CONF_LATITUDE, self.hass.config.latitude
            )
            import_info[CONF_LONGITUDE] = import_info.get(
                CONF_LONGITUDE, self.hass.config.longitude
            )

        import_info[CONF_NAME] = "Imported from yaml"
        for entry in self._async_current_entries(include_ignore=True):
            if entry.source != config_entries.SOURCE_IMPORT:
                continue
            if import_info.get(CONF_COUNTRY_CODE) is not None and import_info[
                CONF_COUNTRY_CODE
            ] == entry.data.get(CONF_COUNTRY_CODE):
                raise data_entry_flow.AbortFlow("already_configured")
            if (
                import_info.get(CONF_LATITUDE) is not None
                and import_info[CONF_LATITUDE] == entry.data.get(CONF_LATITUDE)
                and import_info.get(CONF_LONGITUDE) is not None
                and import_info[CONF_LONGITUDE] == entry.data.get(CONF_LONGITUDE)
            ):
                raise data_entry_flow.AbortFlow("already_configured")

        return await self.async_step_user(import_info)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                vol.Inclusive(CONF_LATITUDE, "coords", msg=MSG_LOCATION): cv.latitude,
                vol.Inclusive(CONF_LONGITUDE, "coords", msg=MSG_LOCATION): cv.longitude,
                vol.Exclusive(CONF_COUNTRY_CODE, "coords"): cv.string,
                vol.Required(CONF_API_KEY): str,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors=errors,
            )

        print(user_input, "----")

        try:
            data = await self.hass.async_add_executor_job(
                CO2Signal.get_latest,
                user_input[CONF_API_KEY],
                user_input.get(CONF_COUNTRY_CODE),
                user_input.get(CONF_LATITUDE),
                user_input.get(CONF_LONGITUDE),
            )
        except ValueError as exp:
            if "Invalid authentication credentials" in str(exp):
                errors["base"] = "invalid_auth"
            else:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if data.get("status") == "ok":
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
