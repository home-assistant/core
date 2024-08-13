"""The waze_travel_time component."""

import asyncio
import logging

from pywaze.route_calculator import CalcRoutesResponse, WazeRouteCalculator, WRCError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_REGION, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_AVOID_FERRIES,
    CONF_AVOID_SUBSCRIPTION_ROADS,
    CONF_AVOID_TOLL_ROADS,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_REALTIME,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_VEHICLE_TYPE,
    DOMAIN,
    METRIC_UNITS,
    REGIONS,
    SEMAPHORE,
    UNITS,
    VEHICLE_TYPES,
)

PLATFORMS = [Platform.SENSOR]

SERVICE_GET_TRAVEL_TIMES = "get_travel_times"
SERVICE_GET_TRAVEL_TIMES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ORIGIN): TextSelector(),
        vol.Required(CONF_DESTINATION): TextSelector(),
        vol.Required(CONF_REGION): SelectSelector(
            SelectSelectorConfig(
                options=REGIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_REGION,
                sort=True,
            )
        ),
        vol.Optional(CONF_REALTIME, default=False): BooleanSelector(),
        vol.Optional(CONF_VEHICLE_TYPE, default=DEFAULT_VEHICLE_TYPE): SelectSelector(
            SelectSelectorConfig(
                options=VEHICLE_TYPES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_VEHICLE_TYPE,
                sort=True,
            )
        ),
        vol.Optional(CONF_UNITS, default=METRIC_UNITS): SelectSelector(
            SelectSelectorConfig(
                options=UNITS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_UNITS,
                sort=True,
            )
        ),
        vol.Optional(CONF_AVOID_TOLL_ROADS, default=False): BooleanSelector(),
        vol.Optional(CONF_AVOID_SUBSCRIPTION_ROADS, default=False): BooleanSelector(),
        vol.Optional(CONF_AVOID_FERRIES, default=False): BooleanSelector(),
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    if SEMAPHORE not in hass.data.setdefault(DOMAIN, {}):
        hass.data.setdefault(DOMAIN, {})[SEMAPHORE] = asyncio.Semaphore(1)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def async_get_travel_times_service(service: ServiceCall) -> ServiceResponse:
        httpx_client = get_async_client(hass)
        client = WazeRouteCalculator(
            region=service.data[CONF_REGION].upper(), client=httpx_client
        )
        response = await async_get_travel_times(
            client=client,
            origin=service.data[CONF_ORIGIN],
            destination=service.data[CONF_DESTINATION],
            vehicle_type=service.data[CONF_VEHICLE_TYPE],
            avoid_toll_roads=service.data[CONF_AVOID_TOLL_ROADS],
            avoid_subscription_roads=service.data[CONF_AVOID_SUBSCRIPTION_ROADS],
            avoid_ferries=service.data[CONF_AVOID_FERRIES],
            realtime=service.data[CONF_REALTIME],
        )
        return {"routes": [vars(route) for route in response]} if response else None

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TRAVEL_TIMES,
        async_get_travel_times_service,
        SERVICE_GET_TRAVEL_TIMES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_get_travel_times(
    client: WazeRouteCalculator,
    origin: str,
    destination: str,
    vehicle_type: str,
    avoid_toll_roads: bool,
    avoid_subscription_roads: bool,
    avoid_ferries: bool,
    realtime: bool,
    incl_filter: str | None = None,
    excl_filter: str | None = None,
) -> list[CalcRoutesResponse] | None:
    """Get all available routes."""

    _LOGGER.debug(
        "Getting update for origin: %s destination: %s",
        origin,
        destination,
    )
    routes = []
    vehicle_type = "" if vehicle_type.upper() == "CAR" else vehicle_type.upper()
    try:
        routes = await client.calc_routes(
            origin,
            destination,
            vehicle_type=vehicle_type,
            avoid_toll_roads=avoid_toll_roads,
            avoid_subscription_roads=avoid_subscription_roads,
            avoid_ferries=avoid_ferries,
            real_time=realtime,
            alternatives=3,
        )

        if incl_filter not in {None, ""}:
            routes = [
                r
                for r in routes
                if any(
                    incl_filter.lower() == street_name.lower()  # type: ignore[union-attr]
                    for street_name in r.street_names
                )
            ]

        if excl_filter not in {None, ""}:
            routes = [
                r
                for r in routes
                if not any(
                    excl_filter.lower() == street_name.lower()  # type: ignore[union-attr]
                    for street_name in r.street_names
                )
            ]

        if len(routes) < 1:
            _LOGGER.warning("No routes found")
            return None
    except WRCError as exp:
        _LOGGER.warning("Error on retrieving data: %s", exp)
        return None

    else:
        return routes


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
