"""Service handlers for the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

from evohomeasync2 import ControlSystem
from evohomeasync2.const import SZ_CAN_BE_TEMPORARY, SZ_SYSTEM_MODE, SZ_TIMING_MODE
from evohomeasync2.schemas.const import (
    S2_DURATION as SZ_DURATION,
    S2_PERIOD as SZ_PERIOD,
)
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE, ATTR_STATE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    service,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import verify_domain_control

from .const import (
    ATTR_DURATION,
    ATTR_PERIOD,
    ATTR_SETPOINT,
    DOMAIN,
    RESET_BREAKS_IN_HA_VERSION,
    SERVICE_BREAKS_IN_HA_VERSION,
    EvoService,
)
from .coordinator import EvoDataUpdateCoordinator
from .helpers import async_create_deprecation_issue_once

# System service schemas (registered as domain services)
SET_SYSTEM_MODE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
    # unsupported modes are rejected at runtime with ServiceValidationError
    vol.Required(ATTR_MODE): cv.string,  # ... so, don't use SystemMode enum here
    vol.Exclusive(ATTR_DURATION, "temporary"): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(hours=0), max=timedelta(hours=24)),
    ),
    vol.Exclusive(ATTR_PERIOD, "temporary"): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(days=1), max=timedelta(days=99)),
    ),
    vol.Optional(ATTR_ENTITY_ID): cv.entity_id,
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

# DHW service schemas (registered as entity services)
SET_DHW_OVERRIDE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
    vol.Required(ATTR_STATE): cv.boolean,
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


def _resolve_ctl_unique_id(
    hass: HomeAssistant,
    call: ServiceCall,
    tcs_id: str,
) -> str:
    """Resolve the target controller unique_id from an optional entity_id.

    During the deprecation window, advise users to switch to targeting the controller.
    """

    if (entity_id := call.data.get(ATTR_ENTITY_ID)) is None:
        async_create_deprecation_issue_once(
            hass,
            f"deprecated_{call.service}_service",
            SERVICE_BREAKS_IN_HA_VERSION,
            translation_key="deprecated_controller_service",
            translation_placeholders={"service": call.service},
        )
        return tcs_id

    entry = er.async_get(hass).async_get(entity_id)

    if entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={ATTR_ENTITY_ID: entity_id},
        )

    # currently, evohome supports only 1 controller
    if (
        entry.domain != CLIMATE_DOMAIN
        or entry.platform != DOMAIN
        or entry.unique_id != tcs_id
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="controller_only_service",
            translation_placeholders={"service": call.service},
        )

    return tcs_id


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


def _validate_set_system_mode_params(tcs: ControlSystem, data: dict[str, Any]) -> None:
    """Validate that a set_system_mode service call is properly formed."""

    mode = data[ATTR_MODE]
    tcs_modes = {m[SZ_SYSTEM_MODE]: m for m in tcs.allowed_system_modes}

    # Validation occurs here, instead of in the library, because it uses a slightly
    # different schema (until instead of duration/period) for the method invoked
    # via this service call

    if (mode_info := tcs_modes.get(mode)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_not_supported",
            translation_placeholders={ATTR_MODE: mode},
        )

    # voluptuous schema ensures that duration and period are not both present

    if not mode_info[SZ_CAN_BE_TEMPORARY]:
        if ATTR_DURATION in data or ATTR_PERIOD in data:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="mode_cant_be_temporary",
                translation_placeholders={ATTR_MODE: mode},
            )
        return

    timing_mode = mode_info.get(SZ_TIMING_MODE)  # will not be None, as can_be_temporary

    if timing_mode == SZ_DURATION and ATTR_PERIOD in data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_cant_have_period",
            translation_placeholders={ATTR_MODE: mode},
        )

    if timing_mode == SZ_PERIOD and ATTR_DURATION in data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="mode_cant_have_duration",
            translation_placeholders={ATTR_MODE: mode},
        )


@callback
def setup_service_functions(
    hass: HomeAssistant, coordinator: EvoDataUpdateCoordinator
) -> None:
    """Set up the service handlers for Evohome systems."""

    @verify_domain_control(DOMAIN)
    async def force_refresh(call: ServiceCall) -> None:
        """Obtain the latest state data via the vendor's RESTful API."""
        await coordinator.async_refresh()

    @verify_domain_control(DOMAIN)
    async def set_system_mode(call: ServiceCall) -> None:
        """Set the Evohome system mode or reset the system."""

        # We can rely upon coordinator.tcs being non-None here, since:
        # - services are registered only if coordinator.async_first_refresh() succeeds
        # - without config flow, the controller entity will never be de-registered

        assert coordinator.tcs is not None  # mypy

        # No additional validation for RESET_SYSTEM here, as the library method invoked
        # via that service call may be able to emulate the reset even if the system
        # doesn't support AutoWithReset natively

        if call.service == EvoService.RESET_SYSTEM:
            async_create_deprecation_issue_once(
                hass,
                "deprecated_reset_system_service",
                RESET_BREAKS_IN_HA_VERSION,
            )

        if call.service == EvoService.SET_SYSTEM_MODE:
            _validate_set_system_mode_params(coordinator.tcs, call.data)
            unique_id = _resolve_ctl_unique_id(hass, call, coordinator.tcs.id)
        else:
            # this service call to be deprecated, so no need to _resolve_ctl_unique_id
            unique_id = coordinator.tcs.id

        payload = {
            "unique_id": unique_id,
            "service": call.service,
            "data": call.data,
        }
        async_dispatcher_send(hass, DOMAIN, payload)

    hass.services.async_register(DOMAIN, EvoService.REFRESH_SYSTEM, force_refresh)
    hass.services.async_register(DOMAIN, EvoService.RESET_SYSTEM, set_system_mode)

    hass.services.async_register(
        DOMAIN,
        EvoService.SET_SYSTEM_MODE,
        set_system_mode,
        schema=vol.Schema(SET_SYSTEM_MODE_SCHEMA),
    )

    _register_zone_entity_services(hass)
    _register_dhw_entity_services(hass)
