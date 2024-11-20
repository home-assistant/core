"""The waze_travel_time component."""

import asyncio
from collections.abc import Collection
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
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_ORIGIN,
    CONF_REALTIME,
    CONF_UNITS,
    CONF_VEHICLE_TYPE,
    DEFAULT_FILTER,
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
    incl_filters: Collection[str] | None = None,
    excl_filters: Collection[str] | None = None,
) -> list[CalcRoutesResponse] | None:
    """Get all available routes."""

    incl_filters = incl_filters or ()
    excl_filters = excl_filters or ()

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
        _LOGGER.debug("Got routes: %s", routes)

        incl_routes: list[CalcRoutesResponse] = []

        def should_include_route(route: CalcRoutesResponse) -> bool:
            if len(incl_filters) < 1:
                return True
            should_include = any(
                street_name in incl_filters or "" in incl_filters
                for street_name in route.street_names
            )
            if not should_include:
                _LOGGER.debug(
                    "Excluding route [%s], because no inclusive filter matched any streetname",
                    route.name,
                )
                return False
            return True

        incl_routes = [route for route in routes if should_include_route(route)]

        filtered_routes: list[CalcRoutesResponse] = []

        def should_exclude_route(route: CalcRoutesResponse) -> bool:
            for street_name in route.street_names:
                for excl_filter in excl_filters:
                    if excl_filter == street_name:
                        _LOGGER.debug(
                            "Excluding route, because exclusive filter [%s] matched streetname: %s",
                            excl_filter,
                            route.name,
                        )
                        return True
            return False

        filtered_routes = [
            route for route in incl_routes if not should_exclude_route(route)
        ]

        if len(filtered_routes) < 1:
            _LOGGER.warning("No routes found")
            return None
    except WRCError as exp:
        _LOGGER.warning("Error on retrieving data: %s", exp)
        return None

    else:
        return filtered_routes


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""

    if config_entry.version == 1:
        _LOGGER.debug(
            "Migrating from version %s.%s",
            config_entry.version,
            config_entry.minor_version,
        )
        options = dict(config_entry.options)
        if (incl_filters := options.pop(CONF_INCL_FILTER, None)) not in {None, ""}:
            options[CONF_INCL_FILTER] = [incl_filters]
        else:
            options[CONF_INCL_FILTER] = DEFAULT_FILTER
        if (excl_filters := options.pop(CONF_EXCL_FILTER, None)) not in {None, ""}:
            options[CONF_EXCL_FILTER] = [excl_filters]
        else:
            options[CONF_EXCL_FILTER] = DEFAULT_FILTER
        hass.config_entries.async_update_entry(config_entry, options=options, version=2)
        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )
    return True
