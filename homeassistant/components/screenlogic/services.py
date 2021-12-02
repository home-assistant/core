"""Services for ScreenLogic integration."""

import logging

from screenlogicpy import ScreenLogicError
from screenlogicpy.const import BODY_TYPE, DATA as SL_DATA, SCG
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import (
    ATTR_COLOR_MODE,
    ATTR_POOL_PERCENT,
    ATTR_SPA_PERCENT,
    DOMAIN,
    SERVICE_SET_COLOR_MODE,
    SERVICE_SET_SCG,
    SUPPORTED_COLOR_MODES,
)

_LOGGER = logging.getLogger(__name__)

MAX_SCG_VALUE_POOL = SCG.LIMIT_FOR_BODY[BODY_TYPE.POOL]
MAX_SCG_VALUE_SPA = SCG.LIMIT_FOR_BODY[BODY_TYPE.SPA]


SET_COLOR_MODE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_COLOR_MODE): vol.In(SUPPORTED_COLOR_MODES),
    },
)

SET_SCG_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional(ATTR_POOL_PERCENT): vol.Clamp(min=0, max=MAX_SCG_VALUE_POOL),
        vol.Optional(ATTR_SPA_PERCENT): vol.Clamp(min=0, max=MAX_SCG_VALUE_SPA),
    }
)


@callback
def async_load_screenlogic_services(hass: HomeAssistant):
    """Set up services for the ScreenLogic integration."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE):
        # Integration-level services have already been added. Return.
        return

    async def extract_screenlogic_config_entry_ids(service_call: ServiceCall):
        return [
            entry_id
            for entry_id in await async_extract_config_entry_ids(hass, service_call)
            if hass.config_entries.async_get_entry(entry_id).domain == DOMAIN
        ]

    async def async_set_color_mode(service_call: ServiceCall):
        if not (
            screenlogic_entry_ids := await extract_screenlogic_config_entry_ids(
                service_call
            )
        ):
            raise HomeAssistantError(
                f"Failed to call service '{SERVICE_SET_COLOR_MODE}'. Config entry for target not found"
            )
        color_num = SUPPORTED_COLOR_MODES[service_call.data[ATTR_COLOR_MODE]]
        for entry_id in screenlogic_entry_ids:
            coordinator = hass.data[DOMAIN][entry_id]
            _LOGGER.debug(
                "Service '%s' called on %s with mode %s",
                SERVICE_SET_COLOR_MODE,
                coordinator.gateway.name,
                color_num,
            )
            try:
                if not await coordinator.gateway.async_set_color_lights(color_num):
                    raise HomeAssistantError(
                        f"Failed to call service '{SERVICE_SET_COLOR_MODE}'"
                    )
                # Debounced refresh to catch any secondary
                # changes in the device
                await coordinator.async_request_refresh()
            except ScreenLogicError as error:
                raise HomeAssistantError(error) from error

    async def async_set_scg(service_call: ServiceCall):
        if not (
            screenlogic_entry_ids := await extract_screenlogic_config_entry_ids(
                service_call
            )
        ):
            raise HomeAssistantError(
                f"Failed to call service '{SERVICE_SET_SCG}'. Config entry for target not found"
            )

        for entry_id in screenlogic_entry_ids:
            coordinator = hass.data[DOMAIN][entry_id]

            pool_value = service_call.data.get(ATTR_POOL_PERCENT)
            spa_value = service_call.data.get(ATTR_SPA_PERCENT)

            if not pool_value and not spa_value:
                raise HomeAssistantError(
                    f"Failed to call service '{SERVICE_SET_SCG}'. No values specified"
                )

            _LOGGER.debug(
                "Service '%s' called on %s with values: Pool: %s, Spa: %s",
                SERVICE_SET_SCG,
                coordinator.gateway.name,
                pool_value if pool_value else "Not set",
                spa_value if spa_value else "Not set",
            )

            if not pool_value:
                pool_value = coordinator.data[SL_DATA.KEY_SCG]["scg_level1"]["value"]

            if not spa_value:
                spa_value = coordinator.data[SL_DATA.KEY_SCG]["scg_level2"]["value"]

            try:
                if not await coordinator.gateway.async_set_scg_config(
                    pool_value, spa_value
                ):
                    raise HomeAssistantError(
                        f"Failed to call service '{SERVICE_SET_SCG}'"
                    )
                # Debounced refresh to catch any secondary
                # changes in the device
                await coordinator.async_request_refresh()
            except ScreenLogicError as error:
                raise HomeAssistantError(error) from error

    hass.services.async_register(
        DOMAIN, SERVICE_SET_COLOR_MODE, async_set_color_mode, SET_COLOR_MODE_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_SET_SCG, async_set_scg, SET_SCG_SCHEMA)


@callback
def async_unload_screenlogic_services(hass: HomeAssistant):
    """Unload services for the ScreenLogic integration."""
    if hass.data[DOMAIN]:
        # There is still another config entry for this domain, don't remove services.
        return

    if not hass.services.has_service(DOMAIN, SERVICE_SET_COLOR_MODE):
        return

    _LOGGER.info("Unloading ScreenLogic Services")
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_SET_COLOR_MODE)
