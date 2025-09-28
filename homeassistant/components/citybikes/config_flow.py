"""Config flow for CityBikes integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_ID, ATTR_NAME, CONF_LOCATION
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
from .sensor import CityBikesNetwork, CityBikesNetworks

_LOGGER = logging.getLogger(__name__)


class CityBikesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CityBikes."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.city_bike_networks: CityBikesNetworks = CityBikesNetworks(self.hass)
        self._data = {
            CONF_NAME: None,
            CONF_NETWORK: None,
            CONF_STATION_FILTER: None,
            CONF_STATIONS_LIST: None,
            CONF_LOCATION: None,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initiated by the user."""

        _LOGGER.debug("async_step_user data: %s", self._data)

        websession = async_get_clientsession(self.hass)
        self.city_bike_networks.session = websession

        if user_input is not None:
            self._data.update(user_input)
            station_filter = self._data[CONF_STATION_FILTER]
            #  fork to different steps depending on mode chosen
            if isinstance(station_filter, list):
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
                            value=n[ATTR_ID],
                            label=n.get(ATTR_NAME, n[ATTR_ID]),
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

        return self.async_show_form(step_id="user", data_schema=vol.Schema(data_schema))

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle an explicit list of stations flow."""

        _LOGGER.debug("async_step_stations data: %s", self._data)

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
                        SelectOptionDict(
                            value=s[ATTR_ID], label=s.get("name", s[ATTR_ID])
                        )
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
    ) -> config_entries.ConfigFlowResult:
        """Handle a stations near me flow."""

        _LOGGER.debug("async_step_radius data: %s", self._data)

        if user_input is not None:
            _LOGGER.debug("Radius user input: %s", user_input[CONF_LOCATION])
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
    # ) -> config_entries.ConfigFlowResult:
    #     """Handle import from YAML."""
    #     pass

    async def async_create(self) -> config_entries.ConfigFlowResult:
        """Create the CityBikes entry entry."""
        _LOGGER.debug("async_create data: %s", self._data)
        title = self._data.get(CONF_NAME, self._data[CONF_NETWORK])
        if title == "" or title is None:
            return self.async_abort(reason="need_name")
        network = self._data.get(CONF_LOCATION, {})
        if network is None:
            network = {}
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
