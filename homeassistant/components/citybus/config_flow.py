"""Config flow to configure the CityBus integration."""

import logging

from citybussin import Citybussin

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_DIRECTION, CONF_ROUTE, CONF_STOP, DOMAIN


_LOGGER = logging.getLogger(__name__)


def _dict_to_select_name_selector(options: dict[str, str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=sorted(
                (
                    SelectOptionDict(value=value, label=value)
                    for key, value in options.items()
                ),
                key=lambda o: o["label"],
            ),
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _dict_to_select_selector(options: dict[str, str]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=sorted(
                (
                    SelectOptionDict(value=key, label=value)
                    for key, value in options.items()
                ),
                key=lambda o: o["label"],
            ),
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _get_routes(citybussin: Citybussin) -> dict[str, str]:
    return {a["key"]: a["shortName"] for a in citybussin.get_bus_routes()}


def _get_route_key_from_route_name(citybussin: Citybussin, route_name: str) -> str:
    return [
        key for key, value in _get_routes(citybussin).items() if value == route_name
    ][0]


def _get_directions(citybussin: Citybussin, route_key: str) -> dict[str, str]:
    return {
        a["direction"]["key"]: a["destination"]
        for a in citybussin.get_route_directions(route_key)
    }


def _get_stops(citybussin: Citybussin, route_key: str) -> dict[str, str]:
    return {a["stopCode"]: a["name"] for a in citybussin.get_route_stops(route_key)}


def _unique_id_from_data(data: dict[str, str]) -> str:
    return f"{data[CONF_ROUTE]}_{data[CONF_DIRECTION]}_{data[CONF_STOP]}"


class CityBusFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle CityBus configuration."""

    VERSION = 1

    _route_key: dict[str, str]
    _direction_key: dict[str, str]
    _stop_code: dict[str, str]

    def __init__(self) -> None:
        """Initialize CityBus config flow."""
        self.data: dict[str, str] = {}
        self._citybussin = Citybussin()

    async def async_step_user(
        self,
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        return await self.async_step_route(user_input)

    async def async_step_route(
        self,
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Select route."""
        if user_input is not None:
            self.data[CONF_ROUTE] = user_input[CONF_ROUTE]

            return await self.async_step_direction()

        self._routes = await self.hass.async_add_executor_job(
            _get_routes, self._citybussin
        )

        return self.async_show_form(
            step_id="route",
            data_schema=vol.Schema(
                {vol.Required(CONF_ROUTE): _dict_to_select_name_selector(self._routes)}
            ),
        )

    async def async_step_direction(
        self,
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Select direction."""
        if user_input is not None:
            self.data[CONF_DIRECTION] = user_input[CONF_DIRECTION]

            return await self.async_step_stop()

        self._route_key = await self.hass.async_add_executor_job(
            _get_route_key_from_route_name, self._citybussin, self.data[CONF_ROUTE]
        )

        self._directions = await self.hass.async_add_executor_job(
            _get_directions, self._citybussin, self._route_key
        )

        return self.async_show_form(
            step_id="direction",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DIRECTION): _dict_to_select_name_selector(
                        self._directions
                    )
                }
            ),
        )

    async def async_step_stop(
        self,
        user_input: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Select stop."""
        if user_input is not None:
            self.data[CONF_STOP] = user_input[CONF_STOP]

            await self.async_set_unique_id(_unique_id_from_data(self.data))
            self._abort_if_unique_id_configured()

            route_name = self.data[CONF_ROUTE]
            direction_destination = self.data[CONF_DIRECTION]

            self._route_key = await self.hass.async_add_executor_job(
                _get_route_key_from_route_name, self._citybussin, route_name
            )

            stop_code = self.data[CONF_STOP]
            stop_name = self._stops[stop_code]

            return self.async_create_entry(
                title=f"{route_name} - {direction_destination} - {stop_name}",
                data=self.data,
            )

        self._stops = await self.hass.async_add_executor_job(
            _get_stops, self._citybussin, self._route_key
        )

        return self.async_show_form(
            step_id="stop",
            data_schema=vol.Schema(
                {vol.Required(CONF_STOP): _dict_to_select_selector(self._stops)}
            ),
        )
