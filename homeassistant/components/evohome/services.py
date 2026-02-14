"""Service handlers for the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

from evohomeasync2.schemas.const import SystemMode as EvoSystemMode
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_MODE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, issue_registry as ir, service
from homeassistant.helpers.service import verify_domain_control

from .const import ATTR_DURATION, ATTR_PERIOD, ATTR_SETPOINT, DOMAIN, EvoService
from .coordinator import EvoDataUpdateCoordinator

_BREAKS_IN_HA_VERSION = "2026.5.0"

# Schema for the optional (until fully deprecated) target in evohome's domain services
_TCS_TARGET_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
    vol.Optional(CONF_ENTITY_ID): vol.All(cv.ensure_list, [cv.entity_id]),
}

# Base schema for set_system_mode (registered as a domain service)
SET_SYSTEM_MODE_BASE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
    vol.Required(CONF_MODE): vol.Coerce(EvoSystemMode),
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
    **_TCS_TARGET_SCHEMA,
}

# Schema for domain-level TCS services with no fields (refresh, reset)
TCS_SERVICE_SCHEMA: Final = vol.Schema(_TCS_TARGET_SCHEMA)

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


# After the deprecation period, these will become entity-level services
def _register_tcs_legacy_services(
    hass: HomeAssistant,
    coordinator: EvoDataUpdateCoordinator,
) -> None:
    """Register domain-level services for the controller (TCS).

    In future, this integration will support multiple controllers, so these services
    will require the controller entity as a target.

    Thus, they will be migrated to entity-level services during a deprecation period.
    Until then:
     - there will be only one controller, so no target will be required
     - no target: issue a deprecation warning but call the service as normal
    """

    def emulate_entity_service(call: ServiceCall) -> None:
        """Emulate the behaviour of an entity-level services.

        Create a deprecation issue if the call has no target entity.
        """

        # if any target entity_id is provided, it must be a controller's; otherwise,
        # issue a warning identical to those in the EvoClimateEntity stub service
        # functions (which are entity-level) that the wrong target type was provided

        if entity_ids := call.data.get(CONF_ENTITY_ID):
            for eid in entity_ids:
                if eid != coordinator.controller_entity.entity_id:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="controller_only_service",
                        translation_placeholders={"service": call.service},
                    )
            return

        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_service_without_target_{call.service}",
            breaks_in_ha_version=_BREAKS_IN_HA_VERSION,
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_service_without_target",
            translation_placeholders={"service": call.service},
        )

    @verify_domain_control(DOMAIN)
    async def handle_refresh(call: ServiceCall) -> None:
        """Obtain the latest state data via the vendor's RESTful API.

        In future, this will be achieved via `homeassistant.update_entity` on a
        location entity (in evohome, a location can have multiple controllers).
        """

        emulate_entity_service(call)
        await coordinator.async_refresh()

    @verify_domain_control(DOMAIN)
    async def handle_reset(call: ServiceCall) -> None:
        """Reset the controller to Auto and all its zones to FollowSchedule."""

        emulate_entity_service(call)
        await coordinator.controller_entity.async_reset_system()

    @verify_domain_control(DOMAIN)
    async def handle_set_mode(call: ServiceCall) -> None:
        """Set the controller to a given mode."""

        emulate_entity_service(call)
        await coordinator.controller_entity.async_set_system_mode(
            call.data[CONF_MODE],
            period=call.data.get(ATTR_PERIOD),
            duration=call.data.get(ATTR_DURATION),
        )

    hass.services.async_register(
        DOMAIN,
        EvoService.REFRESH_SYSTEM,
        handle_refresh,
        schema=TCS_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, EvoService.RESET_SYSTEM, handle_reset, schema=TCS_SERVICE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        EvoService.SET_SYSTEM_MODE,
        handle_set_mode,
        schema=vol.Schema(SET_SYSTEM_MODE_BASE_SCHEMA),
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
    _register_tcs_legacy_services(hass, coordinator)
