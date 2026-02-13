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
from homeassistant.helpers import config_validation as cv, issue_registry as ir, service
from homeassistant.helpers.service import verify_domain_control

from .const import ATTR_DURATION, ATTR_PERIOD, ATTR_SETPOINT, DOMAIN, EvoService
from .coordinator import EvoDataUpdateCoordinator

BREAKS_IN_HA_VERSION: Final = "2026.5.0"

# Controller service schemas (registered as entity services)
SET_CONTROLLER_MODE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
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


@callback
def _async_deprecate_service_call(hass: HomeAssistant, service_name: str) -> None:
    """Create a repairs issue for a deprecated domain-level service call."""

    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_service_{service_name}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        translation_key="deprecated_service",
        translation_placeholders={"service": f"{DOMAIN}.{service_name}"},
    )


def _register_legacy_services(
    hass: HomeAssistant,
    coordinator: EvoDataUpdateCoordinator,
) -> None:
    """Register deprecated domain-level services (no target entity).

    These services exist for backward compatibility and will be removed after the
    deprecation period. Each handler creates a repairs issue to notify the user.
    """

    @verify_domain_control(DOMAIN)
    async def legacy_refresh(call: ServiceCall) -> None:
        """Handle legacy domain-level refresh_system call."""
        _async_deprecate_service_call(hass, call.service)
        await coordinator.controller_entity.async_refresh_system()

    @verify_domain_control(DOMAIN)
    async def legacy_reset(call: ServiceCall) -> None:
        """Handle legacy domain-level reset_system call."""
        _async_deprecate_service_call(hass, call.service)
        await coordinator.controller_entity.async_reset_system()

    @verify_domain_control(DOMAIN)
    async def legacy_set_mode(call: ServiceCall) -> None:
        """Handle legacy domain-level set_system_mode call."""
        _async_deprecate_service_call(hass, call.service)
        await coordinator.controller_entity.async_set_system_mode(
            call.data[ATTR_MODE],
            period=call.data.get(ATTR_PERIOD),
            duration=call.data.get(ATTR_DURATION),
        )

    tcs = coordinator.tcs
    assert tcs is not None  # mypy

    hass.services.async_register(DOMAIN, EvoService.REFRESH_SYSTEM, legacy_refresh)
    hass.services.async_register(DOMAIN, EvoService.RESET_SYSTEM, legacy_reset)

    # Enumerate which operating modes are supported by this system
    if all_modes := [
        m[SZ_SYSTEM_MODE]
        for m in tcs.allowed_system_modes
        if m[SZ_SYSTEM_MODE] != EvoSystemMode.AUTO_WITH_RESET
    ]:
        set_system_mode_schema = SET_CONTROLLER_MODE_SCHEMA | {
            vol.Required(ATTR_MODE): vol.In(all_modes),
        }
        hass.services.async_register(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            legacy_set_mode,
            schema=vol.Schema(set_system_mode_schema),
        )


def _register_entity_services(hass: HomeAssistant) -> None:
    """Register entity-level services for controllers (systems) and zones."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.REFRESH_CONTROLLER,
        entity_domain=CLIMATE_DOMAIN,
        schema={},
        func=f"async_{EvoService.REFRESH_SYSTEM}",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.RESET_CONTROLLER,
        entity_domain=CLIMATE_DOMAIN,
        schema={},
        func=f"async_{EvoService.RESET_SYSTEM}",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_CONTROLLER_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_CONTROLLER_MODE_SCHEMA,
        func=f"async_{EvoService.SET_SYSTEM_MODE}",
    )

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
    """Set up services for the evohome integration.

    Legacy domain-level services are registered here for backward compatibility,
    but they will be removed after the deprecation period.
    """

    _register_entity_services(hass)
    _register_legacy_services(hass, coordinator)
