"""Config flow for WeatherFlow."""
from __future__ import annotations

import asyncio
from asyncio import Future
from asyncio.exceptions import CancelledError
from typing import Any

from pyweatherflow_forecast import (
    WeatherFlow,
    WeatherFlowForecastBadRequest,
    WeatherFlowForecastInternalServerError,
    WeatherFlowForecastUnauthorized,
    WeatherFlowForecastWongStationId,
)
from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.errors import AddressInUseError, EndpointError, ListenerError
import voluptuous as vol
from voluptuous import UNDEFINED

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    _LOGGER,
    CONF_CLOUD_SENSORS,
    CONF_LOCAL_SENSORS,
    CONF_STATION_ID,
    DOMAIN,
    ERROR_MSG_ADDRESS_IN_USE,
    ERROR_MSG_CANNOT_CONNECT,
    ERROR_MSG_NO_DEVICE_FOUND,
)


async def _async_can_discover_devices() -> bool:
    """Return if there are devices that can be discovered."""
    future_event: Future[None] = asyncio.get_running_loop().create_future()

    @callback
    def _async_found(_):
        """Handle a discovered device - only need to do this once so."""

        if not future_event.done():
            future_event.set_result(None)

    async with WeatherFlowListener() as client, asyncio.timeout(10):
        try:
            client.on(EVENT_DEVICE_DISCOVERED, _async_found)
            await future_event
        except asyncio.TimeoutError:
            return False

    return True


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WeatherFlow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry
    ) -> config_entries.OptionsFlow:
        """Get the options flow for WeatherFlow Forecast."""
        return WeatherFlowForecastOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        if user_input is None:
            # Only allow a single instance of integration since the listener
            # will pick up all devices on the network and we don't want to
            # create multiple entries.
            if self._async_current_entries():
                return self.async_abort(reason="single_instance_allowed")
            found_local = False
            errors = {}
            try:
                found_local = await _async_can_discover_devices()
            except AddressInUseError:
                errors["base"] = ERROR_MSG_ADDRESS_IN_USE
            except (ListenerError, EndpointError, CancelledError):
                errors["base"] = ERROR_MSG_CANNOT_CONNECT
            except TimeoutError:
                pass
            if not found_local and not errors:
                errors["base"] = ERROR_MSG_NO_DEVICE_FOUND

            return await self._show_setup_form(
                user_input={CONF_LOCAL_SENSORS: found_local}, errors=errors
            )

        if CONF_STATION_ID in user_input and CONF_API_TOKEN in user_input:
            # If we have user_input lets test it!!
            session = async_create_clientsession(self.hass)
            errors = {}

            try:
                weatherflow_api = WeatherFlow(
                    user_input[CONF_STATION_ID],
                    user_input[CONF_API_TOKEN],
                    session=session,
                )

                station_data = await weatherflow_api.async_get_station()

            except WeatherFlowForecastWongStationId as err:
                _LOGGER.debug(err)
                errors["base"] = "wrong_station_id"
                return await self._show_setup_form(user_input=user_input, errors=errors)
            except WeatherFlowForecastBadRequest as err:
                _LOGGER.debug(err)
                errors["base"] = "bad_request"
                return await self._show_setup_form(user_input=user_input, errors=errors)
            except WeatherFlowForecastInternalServerError as err:
                _LOGGER.debug(err)
                errors["base"] = "server_error"
                return await self._show_setup_form(user_input=user_input, errors=errors)
            except WeatherFlowForecastUnauthorized as err:
                _LOGGER.debug("401 Error: %s", err)
                errors["base"] = "wrong_token"
                return await self._show_setup_form(user_input=user_input, errors=errors)

            await self.async_set_unique_id(user_input[CONF_STATION_ID])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=station_data.station_name,
                data={
                    CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                    CONF_STATION_ID: user_input[CONF_STATION_ID],
                },
                options={CONF_LOCAL_SENSORS: True, CONF_CLOUD_SENSORS: False},
            )

            # Old data which I think we can calculate at startup?
            # return self.async_create_entry(
            #     title=station_data.station_name,
            #     data={
            #         CONF_NAME: station_data.station_name,
            #         CONF_STATION_ID: user_input[CONF_STATION_ID],
            #         CONF_API_TOKEN: user_input[CONF_API_TOKEN],
            #         CONF_DEVICE_ID: station_data.device_id,
            #         CONF_FIRMWARE_REVISION: station_data.firmware_revision,
            #         CONF_SERIAL_NUMBER: station_data.serial_number,
            #     },
            #     options={},
            # )

        else:
            # Create a Local Only config
            return self.async_create_entry(
                title="WeatherFlow",
                data={},
                options={CONF_LOCAL_SENSORS: True, CONF_CLOUD_SENSORS: False},
            )

    async def _show_setup_form(
        self, user_input: dict[str, Any] | None = None, errors=None
    ):
        """Show the setup form to the user."""

        default_station = user_input.get(CONF_STATION_ID, UNDEFINED)
        default_api_token = user_input.get(CONF_API_TOKEN, UNDEFINED)
        found_local = user_input.get(CONF_LOCAL_SENSORS, False)

        if found_local:
            place_holder_text = {
                "note": "NOTE:</br></br>_Local UDP Weather sensors were found._"
            }
        else:
            place_holder_text = {
                "note": "NOTE:</br></br>_Local UDP Weather sensors were **NOT** found._"
            }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_LOCAL_SENSORS, default=found_local): bool,
                    vol.Optional(CONF_STATION_ID, default=default_station): int,
                    vol.Optional(CONF_API_TOKEN, default=default_api_token): str,
                    vol.Optional(CONF_CLOUD_SENSORS, default=False): bool,
                }
            ),
            errors=errors or {},
            description_placeholders=place_holder_text,
        )


class WeatherFlowForecastOptionsFlowHandler(config_entries.OptionsFlow):
    """Options Flow for WeatherFlow Forecast component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the WeatherFlow Forecast Options Flows."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure Options for WeatherFlow Forecast."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCAL_SENSORS,
                        default=self._config_entry.options.get(CONF_LOCAL_SENSORS),
                    ): bool,
                    vol.Required(
                        CONF_CLOUD_SENSORS,
                        default=self._config_entry.options.get(CONF_CLOUD_SENSORS),
                    ): bool,
                    vol.Optional(
                        CONF_STATION_ID,
                        default=self._config_entry.data.get(
                            CONF_CLOUD_SENSORS, UNDEFINED
                        ),
                    ): int,
                    vol.Optional(
                        CONF_API_TOKEN,
                        default=self._config_entry.data.get(
                            CONF_CLOUD_SENSORS, UNDEFINED
                        ),
                    ): str,
                    vol.Optional(CONF_CLOUD_SENSORS, default=False): bool,
                }
            ),
        )
