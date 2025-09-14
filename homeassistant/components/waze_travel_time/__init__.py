"""The waze_travel_time component."""

import asyncio
import logging

from pywaze.route_calculator import WazeRouteCalculator
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_REGION, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.location import find_coordinates
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .config_flow import WazeConfigFlow
from .const import (
    ATTR_DURATION,
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
from .coordinator import WazeTravelTimeCoordinator, async_get_travel_times

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
        vol.Optional(CONF_INCL_FILTER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
        vol.Optional(CONF_EXCL_FILTER): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                multiple=True,
            ),
        ),
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Load the saved entities."""
    if SEMAPHORE not in hass.data.setdefault(DOMAIN, {}):
        hass.data.setdefault(DOMAIN, {})[SEMAPHORE] = asyncio.Semaphore(1)

    httpx_client = get_async_client(hass)
    client = WazeRouteCalculator(
        region=config_entry.data[CONF_REGION].upper(), client=httpx_client
    )

    coordinator = WazeTravelTimeCoordinator(hass, config_entry, client)
    config_entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def async_get_travel_times_service(service: ServiceCall) -> ServiceResponse:
        httpx_client = get_async_client(hass)
        client = WazeRouteCalculator(
            region=service.data[CONF_REGION].upper(), client=httpx_client
        )

        origin_coordinates = find_coordinates(hass, service.data[CONF_ORIGIN])
        destination_coordinates = find_coordinates(hass, service.data[CONF_DESTINATION])

        origin = origin_coordinates if origin_coordinates else service.data[CONF_ORIGIN]
        destination = (
            destination_coordinates
            if destination_coordinates
            else service.data[CONF_DESTINATION]
        )

        response = await async_get_travel_times(
            client=client,
            origin=origin,
            destination=destination,
            vehicle_type=service.data[CONF_VEHICLE_TYPE],
            avoid_toll_roads=service.data[CONF_AVOID_TOLL_ROADS],
            avoid_subscription_roads=service.data[CONF_AVOID_SUBSCRIPTION_ROADS],
            avoid_ferries=service.data[CONF_AVOID_FERRIES],
            realtime=service.data[CONF_REALTIME],
            units=service.data[CONF_UNITS],
            incl_filters=service.data.get(CONF_INCL_FILTER, DEFAULT_FILTER),
            excl_filters=service.data.get(CONF_EXCL_FILTER, DEFAULT_FILTER),
        )
        return {"routes": [vars(route) for route in response]}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TRAVEL_TIMES,
        async_get_travel_times_service,
        SERVICE_GET_TRAVEL_TIMES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""

    if config_entry.version != WazeConfigFlow.VERSION:
        _LOGGER.debug(
            "Migrating config entry %s from version %s to %s",
            config_entry.entry_id,
            config_entry.version,
            WazeConfigFlow.VERSION,
        )

        if config_entry.version == 1:
            options = dict(config_entry.options)
            if (incl_filters := options.pop(CONF_INCL_FILTER, None)) not in {None, ""}:
                options[CONF_INCL_FILTER] = [incl_filters]
            else:
                options[CONF_INCL_FILTER] = DEFAULT_FILTER
            if (excl_filters := options.pop(CONF_EXCL_FILTER, None)) not in {None, ""}:
                options[CONF_EXCL_FILTER] = [excl_filters]
            else:
                options[CONF_EXCL_FILTER] = DEFAULT_FILTER
            hass.config_entries.async_update_entry(
                config_entry, options=options, version=2
            )

        if config_entry.version == 2:
            entity_registry = er.async_get(hass)
            old_unique_id = config_entry.entry_id
            new_unique_id = f"{config_entry.entry_id}_{ATTR_DURATION}"

            if old_entity_id := entity_registry.async_get_entity_id(
                "sensor", DOMAIN, old_unique_id
            ):
                new_entity_id = f"{old_entity_id}_{ATTR_DURATION}"

                _LOGGER.debug(
                    "Migrating unique_id from '%s' to '%s'",
                    old_unique_id,
                    new_unique_id,
                )
                try:
                    _LOGGER.debug(
                        "Migrating entity_id from '%s' to '%s'",
                        old_entity_id,
                        new_entity_id,
                    )
                    entity_registry.async_update_entity(
                        old_entity_id,
                        new_entity_id=new_entity_id,
                        new_unique_id=new_unique_id,
                    )
                except ValueError:
                    _LOGGER.debug(
                        "Cannot change entity_id '%s', updating unique_id only",
                        old_entity_id,
                    )
                    entity_registry.async_update_entity(
                        old_entity_id,
                        new_unique_id=new_unique_id,
                    )
            hass.config_entries.async_update_entry(config_entry, version=3)

    return True
