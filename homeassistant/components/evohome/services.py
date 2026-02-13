"""Service handlers for the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

from evohomeasync2.const import SZ_SYSTEM_MODE
from evohomeasync2.schemas.const import SystemMode as EvoSystemMode
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.service import verify_domain_control

from .const import ATTR_DURATION, ATTR_PERIOD, ATTR_SETPOINT, DOMAIN, EvoService
from .coordinator import EvoDataUpdateCoordinator

# Base schema for set_system_mode (ATTR_MODE is overridden at registration time)
SET_SYSTEM_MODE_BASE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
    vol.Required(ATTR_MODE): vol.Coerce(EvoSystemMode),
    vol.Exclusive(
        ATTR_DURATION,
        "time_constraint",
        msg="Use either duration or period, or neither, but not both",
    ): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(hours=0), max=timedelta(hours=24)),
    ),
    vol.Exclusive(
        ATTR_PERIOD,
        "time_constraint",
        msg="Use either duration or period, or neither, but not both",
    ): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(days=1), max=timedelta(days=99)),
    ),
}

# Zone service schemas (registered as entity services)
CLEAR_ZONE_OVERRIDE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {}
SET_ZONE_OVERRIDE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
    vol.Required(ATTR_SETPOINT): vol.All(
        vol.Coerce(float), vol.Range(min=4.0, max=35.0)
    ),
    vol.Optional(ATTR_DURATION): vol.All(
        cv.time_period, vol.Range(min=timedelta(days=0), max=timedelta(days=1))
    ),
}


def _register_tcs_services(
    hass: HomeAssistant,
    coordinator: EvoDataUpdateCoordinator,
) -> None:
    """Register domain-level services for the controller (TCS)."""

    @verify_domain_control(DOMAIN)
    async def handle_refresh(call: ServiceCall) -> None:
        """Obtain the latest state data via the vendor's RESTful API."""
        await coordinator.async_refresh()

    @verify_domain_control(DOMAIN)
    async def handle_reset(call: ServiceCall) -> None:
        """Reset the system to Auto mode."""
        await coordinator.controller_entity.async_reset_system()

    @verify_domain_control(DOMAIN)
    async def handle_set_mode(call: ServiceCall) -> None:
        """Set the system mode."""
        await coordinator.controller_entity.async_set_system_mode(
            call.data[ATTR_MODE],
            period=call.data.get(ATTR_PERIOD),
            duration=call.data.get(ATTR_DURATION),
        )

    tcs = coordinator.tcs
    assert tcs is not None  # mypy

    hass.services.async_register(DOMAIN, EvoService.REFRESH_SYSTEM, handle_refresh)
    hass.services.async_register(DOMAIN, EvoService.RESET_SYSTEM, handle_reset)

    # Enumerate which operating modes are supported by this system
    if all_modes := [
        m[SZ_SYSTEM_MODE]
        for m in tcs.allowed_system_modes
        if m[SZ_SYSTEM_MODE] != EvoSystemMode.AUTO_WITH_RESET
    ]:
        set_system_mode_schema = SET_SYSTEM_MODE_BASE_SCHEMA | {
            vol.Required(ATTR_MODE): vol.In(all_modes),
        }
        hass.services.async_register(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            handle_set_mode,
            schema=vol.Schema(set_system_mode_schema),
        )


def _register_zone_entity_services(hass: HomeAssistant) -> None:
    """Register entity-level services for zones."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.CLEAR_ZONE_OVERRIDE,
        entity_domain=CLIMATE_DOMAIN,
        schema=CLEAR_ZONE_OVERRIDE_SCHEMA,
        func=f"async_{EvoService.CLEAR_ZONE_OVERRIDE}",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_ZONE_OVERRIDE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_ZONE_OVERRIDE_SCHEMA,
        func=f"async_{EvoService.SET_ZONE_OVERRIDE}",
    )


@callback
def setup_service_functions(
    hass: HomeAssistant, coordinator: EvoDataUpdateCoordinator
) -> None:
    """Set up services for the evohome integration."""

    _register_zone_entity_services(hass)
    _register_tcs_services(hass, coordinator)
