"""Service handlers for the Evohome integration."""

from datetime import timedelta
import re
from typing import Any, Final

from evohomeasync2 import ControlSystem
from evohomeasync2.const import (
    SZ_CAN_BE_TEMPORARY,
    SZ_DURATION,
    SZ_MODE,
    SZ_PERIOD,
    SZ_SETPOINT,
    SZ_STATE,
    SZ_SYSTEM_MODE,
    SZ_TIMING_MODE,
)
import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.service import verify_domain_control

from .const import DOMAIN, EVOHOME_DATA, REFRESH_BREAKS_IN_HA_VERSION, EvoService
from .helpers import async_create_deprecation_issue_once


def as_snake_case(mode: str) -> str:
    """Convert a CamelCase string to the snake_case used by the library."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", mode).lower()


# Controller service schemas (registered as entity services)
SET_SYSTEM_MODE_SCHEMA: Final[dict[str | probatio.Marker, Any]] = {
    # unsupported modes are rejected at runtime with ServiceValidationError
    probatio.Required(SZ_MODE): cv.string,  # ... so, don't use SystemMode enum here
    probatio.Exclusive(SZ_DURATION, "temporary"): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(hours=0), max=timedelta(hours=24)),
    ),
    probatio.Exclusive(SZ_PERIOD, "temporary"): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(days=1), max=timedelta(days=99)),
    ),
}

# Zone service schemas (registered as entity services)
SET_ZONE_OVERRIDE_SCHEMA: Final[dict[str | probatio.Marker, Any]] = {
    probatio.Required(SZ_SETPOINT): probatio.All(
        probatio.Coerce(float), probatio.Range(min=4.0, max=35.0)
    ),
    probatio.Optional(SZ_DURATION): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(days=0), max=timedelta(days=1)),
    ),
}

# DHW service schemas (registered as entity services)
SET_DHW_OVERRIDE_SCHEMA: Final[dict[str | probatio.Marker, Any]] = {
    probatio.Required(SZ_STATE): cv.boolean,
    probatio.Optional(SZ_DURATION): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(days=0), max=timedelta(days=1)),
    ),
}


def _register_ctl_entity_services(hass: HomeAssistant) -> None:
    """Register entity-level services for controllers."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_SYSTEM_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_SYSTEM_MODE_SCHEMA,
        func="async_set_system_mode",
    )


def _register_zone_entity_services(hass: HomeAssistant) -> None:
    """Register entity-level services for zones."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_ZONE_OVERRIDE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_ZONE_OVERRIDE_SCHEMA,
        func="async_set_zone_override",
    )


def _register_dhw_entity_services(hass: HomeAssistant) -> None:
    """Register entity-level services for DHW zones."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        EvoService.SET_DHW_OVERRIDE,
        entity_domain=WATER_HEATER_DOMAIN,
        schema=SET_DHW_OVERRIDE_SCHEMA,
        func="async_set_dhw_override",
    )


def validate_set_system_mode_params(tcs: ControlSystem, data: dict[str, Any]) -> None:
    """Validate that a set_system_mode service call is properly formed."""

    mode = data[SZ_MODE]
    tcs_modes = {m[SZ_SYSTEM_MODE].value: m for m in tcs.allowed_system_modes}

    # Validation occurs here, instead of in the library, because it uses a slightly
    # different schema (until instead of duration/period) for the method invoked
    # via this service call

    if (mode_info := tcs_modes.get(as_snake_case(mode))) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_not_supported",
            translation_placeholders={SZ_MODE: mode},
        )

    # probatio schema ensures that duration and period are not both present

    if not mode_info[SZ_CAN_BE_TEMPORARY]:
        if SZ_DURATION in data or SZ_PERIOD in data:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="mode_cant_be_temporary",
                translation_placeholders={SZ_MODE: mode},
            )
        return

    timing_mode = mode_info.get(SZ_TIMING_MODE)  # will not be None, as can_be_temporary

    if timing_mode == SZ_DURATION and SZ_PERIOD in data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_cant_have_period",
            translation_placeholders={SZ_MODE: mode},
        )

    if timing_mode == SZ_PERIOD and SZ_DURATION in data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_cant_have_duration",
            translation_placeholders={SZ_MODE: mode},
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Evohome services."""

    @verify_domain_control(DOMAIN)
    async def force_refresh(call: ServiceCall) -> None:
        """Obtain the latest state data via the vendor's RESTful API."""
        async_create_deprecation_issue_once(
            hass,
            "deprecated_refresh_system_service",
            REFRESH_BREAKS_IN_HA_VERSION,
        )
        await hass.data[EVOHOME_DATA].coordinator.async_refresh()

    hass.services.async_register(DOMAIN, EvoService.REFRESH_SYSTEM, force_refresh)

    _register_ctl_entity_services(hass)
    _register_zone_entity_services(hass)
    _register_dhw_entity_services(hass)
