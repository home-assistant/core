"""Support for ZoneMinder."""

import logging
from typing import TYPE_CHECKING

import probatio

from homeassistant.const import ATTR_ID, ATTR_NAME, CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

if TYPE_CHECKING:
    from . import ZoneMinderConfigEntry

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_RUN_STATE = "set_run_state"
SET_RUN_STATE_SCHEMA = probatio.Schema(
    {probatio.Required(ATTR_ID): cv.string, probatio.Required(ATTR_NAME): cv.string}
)


async def _async_set_active_state(call: ServiceCall) -> None:
    """Set the ZoneMinder run state to the given state name."""
    zm_id = call.data[ATTR_ID]
    state_name = call.data[ATTR_NAME]
    entries: list[ZoneMinderConfigEntry] = (
        call.hass.config_entries.async_loaded_entries(DOMAIN)
    )
    entry = next((e for e in entries if e.data[CONF_HOST] == zm_id), None)
    if entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_host",
            translation_placeholders={"host": zm_id},
        )
    if not await call.hass.async_add_executor_job(
        entry.runtime_data.client.set_active_state, state_name
    ):
        _LOGGER.error(
            "Unable to change ZoneMinder state. Host: %s, state: %s",
            zm_id,
            state_name,
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register ZoneMinder services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_RUN_STATE,
        _async_set_active_state,
        schema=SET_RUN_STATE_SCHEMA,
    )
