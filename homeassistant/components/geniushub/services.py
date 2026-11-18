"""Setup services for geniushub."""

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import DOMAIN, GeniusHubService
from .schemas import (
    SET_SWITCH_OVERRIDE_SCHEMA,
    SET_ZONE_MODE_SCHEMA,
    SET_ZONE_MODE_SCHEMA_WATER_HEATER,
    SET_ZONE_OVERRIDE_HOT_WATER_SCHEMA,
    SET_ZONE_OVERRIDE_SCHEMA,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services."""

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        GeniusHubService.SET_ZONE_MODE,
        entity_domain=CLIMATE_DOMAIN,
        func=f"async_{GeniusHubService.SET_ZONE_MODE}",
        schema=SET_ZONE_MODE_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        GeniusHubService.SET_ZONE_MODE_WATER_HEATER,
        entity_domain=WATER_HEATER_DOMAIN,
        func=f"async_{GeniusHubService.SET_ZONE_MODE}",
        schema=SET_ZONE_MODE_SCHEMA_WATER_HEATER,
    )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        GeniusHubService.SET_ZONE_OVERRIDE,
        entity_domain=CLIMATE_DOMAIN,
        func=f"async_{GeniusHubService.SET_ZONE_OVERRIDE}",
        schema=SET_ZONE_OVERRIDE_SCHEMA,
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        GeniusHubService.SET_ZONE_OVERRID_WATER_HEATER,
        entity_domain=WATER_HEATER_DOMAIN,
        func=f"async_{GeniusHubService.SET_ZONE_OVERRIDE}",
        schema=SET_ZONE_OVERRIDE_HOT_WATER_SCHEMA,
    )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        GeniusHubService.SET_SWITCH_OVERRIDE,
        entity_domain=SWITCH_DOMAIN,
        func="async_turn_on",
        schema=SET_SWITCH_OVERRIDE_SCHEMA,
    )
