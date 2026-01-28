"""Config flow for CityBikes integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from citybikes.asyncio import Client as CitybikesClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import location as location_util

from .const import CONF_ALL_STATIONS, CONF_NAME, CONF_NETWORK, CONF_RADIUS, CONF_STATIONS_LIST, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def fetch_networks() -> list[dict[str, str]]:
    """Fetch all available networks."""
    client = CitybikesClient()
    try:
        networks = await client.networks.fetch()
        result = []
        for net in networks:
            location_parts = []
            if hasattr(net, "location") and net.location:
                if hasattr(net.location, "city") and net.location.city:
                    location_parts.append(net.location.city)
                if hasattr(net.location, "country") and net.location.country:
                    location_parts.append(net.location.country)
            
            location_str = f" ({', '.join(location_parts)})" if location_parts else ""
            label = f"{net.name}{location_str}"
            
            result.append({
                "id": net.id,
                "name": net.name,
                "label": label,
            })
        return result
    finally:
        await client.close()


class CityBikesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CityBikes."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.network_id: str | None = None
        self.network_name: str | None = None
        self.all_stations: list[dict[str, Any]] = []
        self.filtered_stations: list[dict[str, str]] = []
        self.radius: float = 0.0
        self.latitude: float | None = None
        self.longitude: float | None = None
        self.selected_stations: list[str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - network selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            network_id = user_input.get(CONF_NETWORK)
            if not network_id:
                errors["base"] = "network_required"
            else:
                try:
                    # Validate network and fetch stations
                    client = CitybikesClient()
                    try:
                        network = await client.network(uid=network_id).fetch()
                        self.network_id = network_id
                        self.network_name = network.name
                        
                        # Store network location for default map position
                        if hasattr(network, "location") and network.location:
                            self.latitude = network.location.latitude
                            self.longitude = network.location.longitude
                        else:
                            # Fallback to Home Assistant location if network doesn't have location
                            self.latitude = self.hass.config.latitude
                            self.longitude = self.hass.config.longitude
                        
                        # Store all stations with location data for radius filtering
                        self.all_stations = [
                            {
                                "id": station.id,
                                "name": station.name or f"Station {station.id}",
                                "latitude": station.latitude,
                                "longitude": station.longitude,
                            }
                            for station in network.stations
                        ]
                    finally:
                        await client.close()

                    await self.async_set_unique_id(self.network_id)
                    self._abort_if_unique_id_configured()

                    return await self.async_step_radius()
                except aiohttp.ClientError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"

        # Fetch networks for dropdown
        try:
            networks = await fetch_networks()
            network_options = [
                SelectOptionDict(value=net["id"], label=net["label"])
                for net in networks
            ]
        except Exception:
            _LOGGER.exception("Failed to fetch networks")
            network_options = []
            if not errors:
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_NETWORK): SelectSelector(
                    SelectSelectorConfig(
                        options=network_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        sort=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_radius(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the radius configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Get location from map selector or use network location (already set from network selection)
            location = user_input.get(CONF_LOCATION)
            if location:
                self.latitude = location.get(CONF_LATITUDE, self.latitude or self.hass.config.latitude)
                self.longitude = location.get(CONF_LONGITUDE, self.longitude or self.hass.config.longitude)
                # Get radius from location object (LocationSelector with radius=True includes it)
                radius = location.get(CONF_RADIUS, 1000)
                self.radius = float(radius) if radius else 0.0
            else:
                # Use network location if available, otherwise fallback to Home Assistant location
                if self.latitude is None or self.longitude is None:
                    self.latitude = self.hass.config.latitude
                    self.longitude = self.hass.config.longitude
                self.radius = 0.0
            
            # Filter stations by radius if radius is specified
            if self.radius > 0:
                self.filtered_stations = []
                for station in self.all_stations:
                    dist = location_util.distance(
                        self.latitude,
                        self.longitude,
                        station["latitude"],
                        station["longitude"],
                    )
                    if dist is not None and dist <= self.radius:
                        self.filtered_stations.append({
                            "id": station["id"],
                            "name": station["name"],
                        })
            else:
                # No radius filter - show all stations
                self.filtered_stations = [
                    {"id": station["id"], "name": station["name"]}
                    for station in self.all_stations
                ]
            
            return await self.async_step_stations()

        # Default location to network's location (or Home Assistant's if network location not available) with 1000m radius
        default_location = {
            CONF_LATITUDE: self.latitude or self.hass.config.latitude,
            CONF_LONGITUDE: self.longitude or self.hass.config.longitude,
            CONF_RADIUS: 1000,
        }

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION,
                    default=default_location,
                ): LocationSelector(LocationSelectorConfig(radius=True)),
            }
        )

        return self.async_show_form(
            step_id="radius",
            data_schema=schema,
            errors=errors,
            description_placeholders={"network": self.network_name or "CityBikes"},
        )

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the stations configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store user input for form re-display if there are errors
            if user_input.get(CONF_STATIONS_LIST):
                self.selected_stations = user_input.get(CONF_STATIONS_LIST, [])
            elif user_input.get(CONF_ALL_STATIONS):
                self.selected_stations = []
            all_stations = user_input.get(CONF_ALL_STATIONS, False)
            stations_list = user_input.get(CONF_STATIONS_LIST, [])
            hub_name = user_input.get(CONF_NAME, "")

            # Store selected stations for form re-display
            self.selected_stations = stations_list if isinstance(stations_list, list) else []

            # Make "All stations" and explicit list mutually exclusive
            # If explicit stations are selected, automatically uncheck "All stations"
            if stations_list:
                all_stations = False
            # If "All stations" is enabled, clear the explicit list
            elif all_stations:
                stations_list = []
                self.selected_stations = []

            # Validate that at least one option is selected
            if not all_stations and not stations_list:
                errors["base"] = "no_stations_selected"
            else:
                options: dict[str, Any] = {
                    CONF_ALL_STATIONS: all_stations,
                }
                
                if self.radius > 0:
                    options[CONF_RADIUS] = self.radius
                
                # Store location if it differs from Home Assistant's configured location
                if (self.latitude is not None and self.longitude is not None and
                    (self.latitude != self.hass.config.latitude or
                     self.longitude != self.hass.config.longitude)):
                    options[CONF_LATITUDE] = self.latitude
                    options[CONF_LONGITUDE] = self.longitude
                
                if not all_stations:
                    options[CONF_STATIONS_LIST] = stations_list
                
                title = hub_name.strip() if hub_name else self.network_name or "CityBikes"
                
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_NETWORK: self.network_id,
                    },
                    options=options,
                )

        # Create station options for searchable dropdown from filtered stations
        # Sort stations alphabetically for easier searching
        station_options = sorted(
            [
                SelectOptionDict(value=station["id"], label=station["name"])
                for station in self.filtered_stations
            ],
            key=lambda x: x["label"]
        )

        # Use user_input values if available (form re-display after errors), otherwise use stored state
        if user_input is not None:
            default_all_stations = user_input.get(CONF_ALL_STATIONS, not bool(user_input.get(CONF_STATIONS_LIST, [])))
            default_stations = user_input.get(CONF_STATIONS_LIST, [])
        else:
            # Default "All stations" to False if explicit stations are already selected
            default_all_stations = not bool(self.selected_stations)
            default_stations = self.selected_stations

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME, "") if user_input else ""): TextSelector(),
                vol.Required(CONF_ALL_STATIONS, default=default_all_stations): BooleanSelector(),
                vol.Optional(CONF_STATIONS_LIST, default=default_stations): SelectSelector(
                    SelectSelectorConfig(
                        options=station_options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                        sort=True,
                    )
                ),
            }
        )

        station_count = len(self.filtered_stations)
        radius_info = f" within {int(self.radius)}m" if self.radius > 0 else ""
        return self.async_show_form(
            step_id="stations",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "network": self.network_name or "CityBikes",
                "count": str(station_count),
                "radius": radius_info,
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

