"""Config flow for CityBikes integration."""

import logging
from typing import Any

from citybikes.asyncio import Client as CitybikesClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LOCATION
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_NETWORK,
    CONF_RADIUS,
    CONF_STATION_FILTER,
    CONF_STATIONS_LIST,
    DOMAIN,
)
from .sensor import HA_USER_AGENT, REQUEST_TIMEOUT, CityBikesNetwork, CityBikesNetworks

_LOGGER = logging.getLogger(__name__)


class CityBikesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CityBikes."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.city_bike_networks: CityBikesNetworks = CityBikesNetworks(
            self.hass,
            # TODO: python-citybikes client will create a client session here. This is an issue that needs to be fixed
            client=CitybikesClient(user_agent=HA_USER_AGENT, timeout=REQUEST_TIMEOUT),
        )
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""

        errors: dict[str, str] = {}

        # TODO: python-citybikes client doesn't let us inject a session yet
        self.city_bike_networks.client.session = async_get_clientsession(self.hass)

        if user_input is not None:
            self._data.update(user_input)
            station_filter = self._data[CONF_STATION_FILTER]
            #  fork to different steps depending on mode chosen
            if isinstance(station_filter, list):
                if len(station_filter) == 0:
                    errors[CONF_STATION_FILTER] = "no_station_filter_chosen"
                else:
                    if (
                        CONF_RADIUS in station_filter
                        and self._data.get(CONF_LOCATION) is None
                    ):
                        return await self.async_step_radius()
                    if (
                        CONF_STATIONS_LIST in station_filter
                        and self._data.get(CONF_STATIONS_LIST) is None
                    ):
                        return await self.async_step_stations()
                    return await self.async_create()

        try:
            await self.city_bike_networks.load_networks()
            if self.city_bike_networks.networks is None:
                return self.async_abort(reason="cannot_connect")
        except PlatformNotReady:
            return self.async_abort(reason="cannot_connect")

        default_network_id = await self.city_bike_networks.get_closest_network_id(
            self.hass.config.latitude, self.hass.config.longitude
        )

        _LOGGER.debug(
            "Found %d networks. Closest is %s",
            len(self.city_bike_networks.networks),
            default_network_id,
        )

        data_schema = {
            vol.Required(CONF_NETWORK, default=default_network_id): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            value=n.id,
                            label=f"{(n.name or n.id)} ({n.location.city or 'unknown city'}, {n.location.country or 'unknown country'})",
                        )
                        for n in self.city_bike_networks.networks
                    ],
                    multiple=False,
                    sort=True,
                )
            ),
            vol.Required(CONF_STATION_FILTER, default=[CONF_RADIUS]): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            value=CONF_RADIUS,
                            label="All stations within location/home radius",
                        ),
                        SelectOptionDict(
                            value=CONF_STATIONS_LIST,
                            label="Explicit list of stations",
                        ),
                    ],
                    multiple=True,
                )
            ),
            vol.Optional(CONF_NAME, default=""): cv.string,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(data_schema), errors=errors
        )

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an explicit list of stations flow."""

        network_id = self._data[CONF_NETWORK]
        if network_id is None:
            return self.async_abort(reason="no_network_chosen")

        network = CityBikesNetwork(self.hass, network_id)
        try:
            await network.async_refresh(now=True)
        except PlatformNotReady:
            return self.async_abort(reason="cannot_connect")

        _LOGGER.debug(
            "Found %d stations in network %s", len(network.stations), network_id
        )

        if user_input is not None:
            self._data.update(user_input)
            _LOGGER.debug(
                "User chose %d stations: %s",
                len(user_input[CONF_STATIONS_LIST]),
                user_input[CONF_STATIONS_LIST],
            )
            station_filter = self._data[CONF_STATION_FILTER]
            if (
                isinstance(station_filter, list)
                and CONF_RADIUS in station_filter
                and self._data.get(CONF_LOCATION) is None
            ):
                return await self.async_step_radius()
            return await self.async_create()

        data_schema = {
            vol.Required(CONF_STATIONS_LIST, default=[]): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=s.id, label=(s.name or s.id))
                        for s in network.stations
                    ],
                    multiple=True,
                    sort=True,
                )
            ),
        }

        return self.async_show_form(
            step_id="stations", data_schema=vol.Schema(data_schema)
        )

    async def async_step_radius(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a stations near me flow."""

        if user_input is not None:
            self._data.update(user_input)
            station_filter = self._data[CONF_STATION_FILTER]
            if (
                isinstance(station_filter, list)
                and CONF_STATIONS_LIST in station_filter
                and self._data.get(CONF_STATIONS_LIST) is None
            ):
                return await self.async_step_stations()
            return await self.async_create()

        data_schema = {
            vol.Required(
                CONF_LOCATION,
                default={
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                    CONF_RADIUS: 1000,
                },
            ): LocationSelector(LocationSelectorConfig(radius=True)),
        }

        return self.async_show_form(
            step_id="radius", data_schema=vol.Schema(data_schema)
        )

    # async def async_step_import(
    #     self, import_config: dict[str, Any]
    # ) -> ConfigFlowResult:
    #     """Handle import from YAML."""
    #     pass

    async def async_create(self) -> ConfigFlowResult:
        """Create the CityBikes entry entry."""
        title = self._data.get(CONF_NAME)
        if title == "" or title is None:
            title = self._data[CONF_NETWORK]
        if title is None:
            return self.async_abort(reason="need_name")
        network = self._data.get(CONF_LOCATION, {})
        if network is None:
            network = {}
        _LOGGER.debug("Creating entry with title %s: %s", title, self._data)
        return self.async_create_entry(
            title=title,
            data={
                CONF_NAME: self._data[CONF_NAME],
                CONF_NETWORK: self._data[CONF_NETWORK],
                CONF_STATION_FILTER: self._data[CONF_STATION_FILTER],
                CONF_STATIONS_LIST: self._data.get(CONF_STATIONS_LIST),
                CONF_LOCATION: self._data.get(CONF_LOCATION),
                CONF_RADIUS: network.get(CONF_RADIUS),
                CONF_LATITUDE: network.get(CONF_LATITUDE),
                CONF_LONGITUDE: network.get(CONF_LONGITUDE),
            },
        )
