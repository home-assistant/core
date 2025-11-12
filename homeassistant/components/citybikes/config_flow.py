"""Config flow for CityBikes integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from citybikes.asyncio import Client as CitybikesClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import location as location_util

from .const import CONF_NETWORK, CONF_RADIUS, CONF_STATIONS_LIST, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NETWORK, default=""): str,
    }
)

STEP_STATIONS_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_RADIUS): NumberSelector(
            NumberSelectorConfig(
                min=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="m",
            )
        ),
        vol.Optional(CONF_STATIONS_LIST): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    client = CitybikesClient()
    network_id = data.get(CONF_NETWORK)

    try:
        if network_id:
            network = await client.network(uid=network_id).fetch()
        else:
            # Find closest network
            latitude = data.get(CONF_LATITUDE, hass.config.latitude)
            longitude = data.get(CONF_LONGITUDE, hass.config.longitude)
            networks = await client.networks.fetch()
            if not networks:
                raise CannotConnect("No networks available")

            minimum_dist = None
            network = None
            for net in networks:
                net_lat = net.location.latitude
                net_lng = net.location.longitude
                dist = location_util.distance(
                    latitude, longitude, net_lat, net_lng
                )
                if minimum_dist is None or dist < minimum_dist:
                    minimum_dist = dist
                    network = net
                    network_id = net.id

            if network is None:
                raise CannotConnect("Could not find a network")

        return {
            "network_id": network_id,
            "network_name": network.name,
            "title": network.name,
        }
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Error connecting to CityBikes API: {err}") from err
    finally:
        await client.close()


class CityBikesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CityBikes."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.network_id: str | None = None
        self.network_name: str | None = None
        self.station_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # If network is empty string, treat as None
            if not user_input.get(CONF_NETWORK):
                user_input[CONF_NETWORK] = None
            
            try:
                info = await validate_input(self.hass, user_input)
                self.network_id = info["network_id"]
                self.network_name = info["network_name"]

                await self.async_set_unique_id(self.network_id)
                self._abort_if_unique_id_configured()

                return await self.async_step_stations()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the stations configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that at least one filter is provided
            if not user_input.get(CONF_RADIUS) and not user_input.get(CONF_STATIONS_LIST):
                errors["base"] = "no_station_filter"
            else:
                self.station_config = user_input
                return self.async_create_entry(
                    title=self.network_name or "CityBikes",
                    data={
                        CONF_NETWORK: self.network_id,
                    },
                    options=self.station_config,
                )

        return self.async_show_form(
            step_id="stations",
            data_schema=STEP_STATIONS_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"network": self.network_name or "CityBikes"},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

