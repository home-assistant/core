"""Service handlers for the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

from evohomeasync2.const import SZ_CAN_BE_TEMPORARY, SZ_SYSTEM_MODE, SZ_TIMING_MODE
from evohomeasync2.schemas.const import (
    S2_DURATION as SZ_DURATION,
    S2_PERIOD as SZ_PERIOD,
    SystemMode as EvoSystemMode,
)
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import verify_domain_control

from .const import ATTR_DURATION, ATTR_PERIOD, ATTR_SETPOINT, DOMAIN, EvoService
from .coordinator import EvoDataUpdateCoordinator

# system mode schemas are built dynamically when the services are registered
# because supported modes can vary for edge-case systems

# Zone service schemas (registered as entity services)
CLEAR_ZONE_OVERRIDE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {}
SET_ZONE_OVERRIDE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
    vol.Required(ATTR_SETPOINT): vol.All(
        vol.Coerce(float), vol.Range(min=4.0, max=35.0)
    ),
    vol.Optional(ATTR_DURATION): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(days=0), max=timedelta(days=1)),
    ),
}


def _register_zone_entity_services(hass: HomeAssistant) -> None:
    """Register entity-level services for zones."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.CLEAR_ZONE_OVERRIDE,
        entity_domain=CLIMATE_DOMAIN,
        schema=CLEAR_ZONE_OVERRIDE_SCHEMA,
        func="async_clear_zone_override",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_ZONE_OVERRIDE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_ZONE_OVERRIDE_SCHEMA,
        func="async_set_zone_override",
    )


@callback
def setup_service_functions(
    hass: HomeAssistant, coordinator: EvoDataUpdateCoordinator
) -> None:
    """Set up the service handlers for the system/zone operating modes.

    Not all Honeywell TCC-compatible systems support all operating modes. In addition,
    each mode will require any of four distinct service schemas. This has to be
    enumerated before registering the appropriate handlers.
    """

    @verify_domain_control(DOMAIN)
    async def force_refresh(call: ServiceCall) -> None:
        """Obtain the latest state data via the vendor's RESTful API."""
        await coordinator.async_refresh()

    @verify_domain_control(DOMAIN)
    async def set_system_mode(call: ServiceCall) -> None:
        """Set the system mode."""
        assert coordinator.tcs is not None  # mypy

        payload = {
            "unique_id": coordinator.tcs.id,
            "service": call.service,
            "data": call.data,
        }
        async_dispatcher_send(hass, DOMAIN, payload)

    assert coordinator.tcs is not None  # mypy

    hass.services.async_register(DOMAIN, EvoService.REFRESH_SYSTEM, force_refresh)

    # Enumerate which operating modes are supported by this system
    modes = list(coordinator.tcs.allowed_system_modes)

    # Not all systems support "AutoWithReset": register this handler only if required
    if any(
        m[SZ_SYSTEM_MODE]
        for m in modes
        if m[SZ_SYSTEM_MODE] == EvoSystemMode.AUTO_WITH_RESET
    ):
        hass.services.async_register(DOMAIN, EvoService.RESET_SYSTEM, set_system_mode)

    system_mode_schemas = []
    modes = [m for m in modes if m[SZ_SYSTEM_MODE] != EvoSystemMode.AUTO_WITH_RESET]

    # Permanent-only modes will use this schema
    perm_modes = [m[SZ_SYSTEM_MODE] for m in modes if not m[SZ_CAN_BE_TEMPORARY]]
    if perm_modes:  # any of: "Auto", "HeatingOff": permanent only
        schema = vol.Schema({vol.Required(ATTR_MODE): vol.In(perm_modes)})
        system_mode_schemas.append(schema)

    modes = [m for m in modes if m[SZ_CAN_BE_TEMPORARY]]

    # These modes are set for a number of hours (or indefinitely): use this schema
    temp_modes = [m[SZ_SYSTEM_MODE] for m in modes if m[SZ_TIMING_MODE] == SZ_DURATION]
    if temp_modes:  # any of: "AutoWithEco", permanent or for 0-24 hours
        schema = vol.Schema(
            {
                vol.Required(ATTR_MODE): vol.In(temp_modes),
                vol.Optional(ATTR_DURATION): vol.All(
                    cv.time_period,
                    vol.Range(min=timedelta(hours=0), max=timedelta(hours=24)),
                ),
            }
        )
        system_mode_schemas.append(schema)

    # These modes are set for a number of days (or indefinitely): use this schema
    temp_modes = [m[SZ_SYSTEM_MODE] for m in modes if m[SZ_TIMING_MODE] == SZ_PERIOD]
    if temp_modes:  # any of: "Away", "Custom", "DayOff", permanent or for 1-99 days
        schema = vol.Schema(
            {
                vol.Required(ATTR_MODE): vol.In(temp_modes),
                vol.Optional(ATTR_PERIOD): vol.All(
                    cv.time_period,
                    vol.Range(min=timedelta(days=1), max=timedelta(days=99)),
                ),
            }
        )
        system_mode_schemas.append(schema)

    if system_mode_schemas:
        hass.services.async_register(
            DOMAIN,
            EvoService.SET_SYSTEM_MODE,
            set_system_mode,
            schema=vol.Schema(vol.Any(*system_mode_schemas)),
        )

    _register_zone_entity_services(hass)
