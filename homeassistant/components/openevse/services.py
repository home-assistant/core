"""Services for the OpenEVSE integration."""

from typing import Any, Final

import probatio

from homeassistant.const import ATTR_STATE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import OpenEVSEConfigEntry
from .helpers import openevse_exception_handler

ATTR_CHARGE_CURRENT: Final = "charge_current"
ATTR_MAX_CURRENT: Final = "max_current"
ATTR_ENERGY_LIMIT: Final = "energy_limit"
ATTR_TIME_LIMIT: Final = "time_limit"
ATTR_AUTO_RELEASE: Final = "auto_release"

OVERRIDE_STATES: Final = ["active", "disabled"]

SET_OVERRIDE_SCHEMA: Final = cv.make_entity_service_schema(
    {
        probatio.Optional(ATTR_STATE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=OVERRIDE_STATES,
                translation_key="override_state",
            )
        ),
        probatio.Optional(ATTR_CHARGE_CURRENT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=6,
                max=80,
                step=1,
                unit_of_measurement="A",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        probatio.Optional(ATTR_MAX_CURRENT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=6,
                max=80,
                step=1,
                unit_of_measurement="A",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        probatio.Optional(ATTR_ENERGY_LIMIT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                step=1,
                unit_of_measurement="Wh",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        probatio.Optional(ATTR_TIME_LIMIT): selector.DurationSelector(
            selector.DurationSelectorConfig(allow_negative=False)
        ),
        probatio.Optional(ATTR_AUTO_RELEASE): selector.BooleanSelector(),
    }
)

TARGET_ONLY_SCHEMA: Final = cv.make_entity_service_schema({})


async def _async_get_entries(call: ServiceCall) -> list[OpenEVSEConfigEntry]:
    """Resolve loaded config entries targeted by a service call."""
    target_entry_ids = await async_extract_config_entry_ids(call)
    entries: list[OpenEVSEConfigEntry] = [
        entry
        for entry in call.hass.config_entries.async_loaded_entries(DOMAIN)
        if entry.entry_id in target_entry_ids
    ]
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_matching_target_entries",
        )
    return entries


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for OpenEVSE."""

    async def async_set_override(call: ServiceCall) -> None:
        """Set manual override."""
        entries = await _async_get_entries(call)
        time_limit = call.data.get(ATTR_TIME_LIMIT)
        time_limit_seconds: int | None = (
            max(1, round(cv.positive_time_period(time_limit).total_seconds()))
            if time_limit is not None
            else None
        )

        for entry in entries:
            coordinator = entry.runtime_data
            with openevse_exception_handler(call.data):
                await coordinator.charger.set_override(
                    state=call.data.get(ATTR_STATE),
                    charge_current=call.data.get(ATTR_CHARGE_CURRENT),
                    max_current=call.data.get(ATTR_MAX_CURRENT),
                    energy_limit=call.data.get(ATTR_ENERGY_LIMIT),
                    time_limit=time_limit_seconds,
                    auto_release=call.data.get(ATTR_AUTO_RELEASE),
                )
            await coordinator.async_request_refresh()

    async def async_clear_override(call: ServiceCall) -> None:
        """Clear manual override."""
        entries = await _async_get_entries(call)
        for entry in entries:
            coordinator = entry.runtime_data
            with openevse_exception_handler(call.data):
                await coordinator.charger.clear_override()
            await coordinator.async_request_refresh()

    async def async_get_override(call: ServiceCall) -> ServiceResponse:
        """Get manual override details."""
        entries = await _async_get_entries(call)
        if len(entries) > 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="multiple_target_entries",
            )
        coordinator = entries[0].runtime_data

        with openevse_exception_handler(call.data):
            override_data: Any = await coordinator.charger.get_override()

        if isinstance(override_data, dict):
            return dict(override_data)
        return {"override": override_data}

    hass.services.async_register(
        DOMAIN,
        "set_override",
        async_set_override,
        schema=SET_OVERRIDE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        "clear_override",
        async_clear_override,
        schema=TARGET_ONLY_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        "get_override",
        async_get_override,
        schema=TARGET_ONLY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
