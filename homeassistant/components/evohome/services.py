"""Service handlers for the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

import evohomeasync2 as ec2
from evohomeasync2.const import SZ_CAN_BE_TEMPORARY, SZ_SYSTEM_MODE, SZ_TIMING_MODE
from evohomeasync2.schemas.const import S2_DURATION, S2_PERIOD
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import verify_domain_control

from .const import ATTR_DURATION, ATTR_PERIOD, ATTR_SETPOINT, DOMAIN, EvoService
from .coordinator import EvoDataUpdateCoordinator

# System service schemas (registered as domain services)
SET_SYSTEM_MODE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
    vol.Required(ATTR_MODE): str,  # avoid vol.In(SystemMode)
    vol.Exclusive(ATTR_DURATION, "temporary"): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(hours=0), max=timedelta(hours=24)),
    ),
    vol.Exclusive(ATTR_PERIOD, "temporary"): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(days=1), max=timedelta(days=99)),
    ),
}

# Zone service schemas (registered as entity services)
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
        schema=None,
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


def _validate_set_system_mode_params(call: ServiceCall, tcs: ec2.ControlSystem) -> None:
    """Validate that a set_system_mode service call is properly formed."""

    mode = call.data[ATTR_MODE]
    evo_modes = {m[SZ_SYSTEM_MODE]: m for m in tcs.allowed_system_modes}

    if (mode_info := evo_modes.get(mode)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_not_supported",
            translation_placeholders={ATTR_MODE: mode},
        )

    if not mode_info[SZ_CAN_BE_TEMPORARY]:
        if ATTR_DURATION in call.data or ATTR_PERIOD in call.data:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="mode_cant_be_temporary",
                translation_placeholders={ATTR_MODE: mode},
            )

    elif mode_info[SZ_TIMING_MODE] == S2_DURATION and ATTR_PERIOD in call.data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_cant_have_period",
            translation_placeholders={ATTR_MODE: mode},
        )

    elif mode_info[SZ_TIMING_MODE] == S2_PERIOD and ATTR_DURATION in call.data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_cant_have_duration",
            translation_placeholders={ATTR_MODE: mode},
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
        """Set the system mode or reset the system."""

        if call.service == EvoService.SET_SYSTEM_MODE:  # no validation for RESET_SYSTEM
            _validate_set_system_mode_params(call, coordinator.tcs)

        payload = {
            "unique_id": coordinator.tcs.id,
            "service": call.service,
            "data": call.data,
        }
        async_dispatcher_send(hass, DOMAIN, payload)

    assert coordinator.tcs is not None  # mypy

    hass.services.async_register(DOMAIN, EvoService.REFRESH_SYSTEM, force_refresh)
    hass.services.async_register(DOMAIN, EvoService.RESET_SYSTEM, set_system_mode)

    hass.services.async_register(
        DOMAIN,
        EvoService.SET_SYSTEM_MODE,
        set_system_mode,
        schema=vol.Schema(SET_SYSTEM_MODE_SCHEMA),
    )

    _register_zone_entity_services(hass)
