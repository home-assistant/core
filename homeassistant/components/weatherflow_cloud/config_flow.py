"""Config flow for WeatherflowCloud integration."""
from __future__ import annotations

from typing import Any

from pyweatherflow_forecast import (
    WeatherFlow,
    WeatherFlowForecastBadRequest,
    WeatherFlowForecastInternalServerError,
    WeatherFlowForecastUnauthorized,
    WeatherFlowForecastWongStationId,
    WeatherFlowStationData,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_DEVICE_ID, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    _LOGGER,
    CONF_FIRMWARE_REVISION,
    CONF_SERIAL_NUMBER,
    CONF_STATION_ID,
    DOMAIN,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WeatherFlowCloud."""

    VERSION = 1

    async def _async_validate_and_get_station_info(
        self, station_id: int, api_token: str
    ) -> WeatherFlowStationData:
        """Validate credentials and obtain station information."""

        session = async_create_clientsession(self.hass)
        api = WeatherFlow(station_id, api_token, session)
        station_info = await api.async_get_station()
        return station_info

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        if user_input is None:
            return await self._show_setup_form(user_input)

        errors = {}

        try:
            station_data = await self._async_validate_and_get_station_info(
                user_input[CONF_STATION_ID], user_input[CONF_API_TOKEN]
            )
        except WeatherFlowForecastWongStationId as err:
            _LOGGER.debug(err)
            errors["base"] = "wrong_station_id"
            return await self._show_setup_form(errors)
        except WeatherFlowForecastBadRequest as err:
            _LOGGER.debug(err)
            errors["base"] = "bad_request"
            return await self._show_setup_form(errors)
        except WeatherFlowForecastInternalServerError as err:
            _LOGGER.debug(err)
            errors["base"] = "server_error"
            return await self._show_setup_form(errors)
        except WeatherFlowForecastUnauthorized as err:
            _LOGGER.debug("401 Error: %s", err)
            errors["base"] = "wrong_token"
            return await self._show_setup_form(errors)

        await self.async_set_unique_id(user_input[CONF_STATION_ID])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=station_data.station_name,
            data={
                CONF_NAME: station_data.station_name,
                CONF_STATION_ID: user_input[CONF_STATION_ID],
                CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                CONF_DEVICE_ID: station_data.device_id,
                CONF_FIRMWARE_REVISION: station_data.firmware_revision,
                CONF_SERIAL_NUMBER: station_data.serial_number,
            },
        )

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATION_ID): int, vol.Required(CONF_API_TOKEN): str}
            ),
            errors=errors or {},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
