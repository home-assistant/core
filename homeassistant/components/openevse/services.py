"""Services for the OpenEVSE integration."""

from enum import StrEnum
from typing import Final

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .coordinator import OpenEVSEConfigEntry
from .helpers import openevse_exception_handler


class OpenEVSEService(StrEnum):
    """Store keys for OpenEVSE services."""

    SET_OVERRIDE = "set_override"


class OpenEVSEServiceArgument(StrEnum):
    """Store keys for OpenEVSE service arguments."""

    AUTO_RELEASE = "auto_release"
    CHARGE_CURRENT = "charge_current"
    ENERGY_LIMIT = "energy_limit"
    MAX_CURRENT = "max_current"
    STATE = "state"
    TIME_LIMIT = "time_limit"


OVERRIDE_STATES: Final = ["active", "disabled"]

SET_OVERRIDE_SCHEMA: Final = cv.make_entity_service_schema(
    {
        probatio.Optional(OpenEVSEServiceArgument.STATE): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=OVERRIDE_STATES,
                translation_key="override_state",
            )
        ),
        probatio.Optional(
            OpenEVSEServiceArgument.CHARGE_CURRENT
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=6,
                max=80,
                step=1,
                unit_of_measurement="A",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        probatio.Optional(OpenEVSEServiceArgument.MAX_CURRENT): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=6,
                max=80,
                step=1,
                unit_of_measurement="A",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        probatio.Optional(
            OpenEVSEServiceArgument.ENERGY_LIMIT
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                step=1,
                unit_of_measurement="Wh",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        probatio.Optional(
            OpenEVSEServiceArgument.TIME_LIMIT
        ): selector.DurationSelector(
            selector.DurationSelectorConfig(allow_negative=False)
        ),
        probatio.Optional(
            OpenEVSEServiceArgument.AUTO_RELEASE
        ): selector.BooleanSelector(),
    }
)


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
        time_limit = call.data.get(OpenEVSEServiceArgument.TIME_LIMIT)
        time_limit_seconds: int | None = (
            max(1, round(cv.positive_time_period(time_limit).total_seconds()))
            if time_limit is not None
            else None
        )

        for entry in entries:
            coordinator = entry.runtime_data
            with openevse_exception_handler(call.data):
                await coordinator.charger.set_override(
                    state=call.data.get(OpenEVSEServiceArgument.STATE),
                    charge_current=call.data.get(
                        OpenEVSEServiceArgument.CHARGE_CURRENT
                    ),
                    max_current=call.data.get(OpenEVSEServiceArgument.MAX_CURRENT),
                    energy_limit=call.data.get(OpenEVSEServiceArgument.ENERGY_LIMIT),
                    time_limit=time_limit_seconds,
                    auto_release=call.data.get(OpenEVSEServiceArgument.AUTO_RELEASE),
                )
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        OpenEVSEService.SET_OVERRIDE,
        async_set_override,
        schema=SET_OVERRIDE_SCHEMA,
    )
