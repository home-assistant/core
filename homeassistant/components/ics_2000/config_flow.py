"""Config flow for the KlikAanKlikUit ICS-2000 integration."""

from __future__ import annotations

import logging
from typing import Any

from ics_2000.exceptions import InvalidAuthException
from ics_2000.hub import Hub
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import CONF_HOME_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_IP_ADDRESS): str,
    }
)


async def validate_auth(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[Hub, dict[str, str]]:
    """Validate the user input allows us to connect."""
    hub = Hub(data[CONF_USERNAME], data[CONF_PASSWORD])
    hub.local_address = data.get(CONF_IP_ADDRESS)
    try:
        homes = await hass.async_add_executor_job(hub.login)
    except InvalidAuthException as exs:
        raise InvalidAuth from exs
    return hub, homes


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    hub, homes = await validate_auth(hass, data)

    home_id = data.get(CONF_HOME_ID)
    if home_id is not None and home_id in homes:
        await hass.async_add_executor_job(hub.select_home, home_id)
    else:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": homes[home_id], "id": home_id}


class Ics2000ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KlikAanKlikUit ICS-2000."""

    def __init__(self) -> None:
        """Initialize ics-2000 config flow."""
        self._existing_entry_data: dict[str, Any] = {}

    VERSION = 1
    MINOR_VERSION = 1

    async def _async_select_home(self, homes: dict[str, str]) -> ConfigFlowResult:
        options = [
            selector.SelectOptionDict(value=home_id, label=home_name)
            for home_id, home_name in homes.items()
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_HOME_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="home", data_schema=schema)

    async def _validate_and_create_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            combined_input = {**self._existing_entry_data, **user_input}
            if combined_input.get(CONF_HOME_ID) is None:
                self._existing_entry_data = {**user_input}
                _, homes = await validate_auth(self.hass, combined_input)
                if len(homes) > 1:
                    return await self._async_select_home(homes)
                combined_input[CONF_HOME_ID] = next(iter(homes))
            try:
                info = await validate_input(self.hass, combined_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=combined_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_home(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the home selection step."""
        return await self._validate_and_create_entry(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self._validate_and_create_entry(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
