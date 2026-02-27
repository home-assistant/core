"""Service handlers for the Evohome integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

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
SET_ZONE_OVERRIDE_SCHEMA: Final[dict[str | vol.Marker, Any]] = {
    vol.Required(ATTR_SETPOINT): vol.All(
        vol.Coerce(float), vol.Range(min=4.0, max=35.0)
    ),
    vol.Optional(ATTR_DURATION): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(days=0), max=timedelta(days=1)),
    ),
}
# TCS (system/controller) service schemas (registered as domain services)
SET_SYSTEM_MODE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_MODE): str,
        vol.Exclusive(ATTR_DURATION, "temporary"): vol.All(
            cv.time_period,
            vol.Range(min=timedelta(hours=0), max=timedelta(hours=24)),
        ),
        vol.Exclusive(ATTR_PERIOD, "temporary"): vol.All(
            cv.time_period,
            vol.Range(min=timedelta(days=1), max=timedelta(days=99)),
        ),
    }
)


@callback
def setup_service_functions(
    hass: HomeAssistant, coordinator: EvoDataUpdateCoordinator
) -> None:
    """Set up the service handlers for the system/zone operating modes."""

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

    hass.services.async_register(
        DOMAIN,
        EvoService.REFRESH_SYSTEM,
        force_refresh,
    )

    hass.services.async_register(
        DOMAIN,
        EvoService.RESET_SYSTEM,
        set_system_mode,
    )

    hass.services.async_register(
        DOMAIN,
        EvoService.SET_SYSTEM_MODE,
        set_system_mode,
        schema=SET_SYSTEM_MODE_SCHEMA,
    )

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
