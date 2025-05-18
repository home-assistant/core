"""Services for the bosch_alarm integration."""

from __future__ import annotations

import asyncio
import datetime as dt

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    DATETIME_ATTR,
    DOMAIN,
    SET_DATE_TIME_SERVICE_NAME,
)
from .types import BoschAlarmConfigEntry

SET_DATE_TIME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(DATETIME_ATTR): cv.datetime,
    }
)


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the bosch alarm integration."""

    async def async_set_panel_date(call: ServiceCall) -> None:
        """Set the date and time on a bosch alarm panel."""
        config_entry: BoschAlarmConfigEntry | None
        value: dt.datetime = call.data.get(DATETIME_ATTR, dt_util.now())
        entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
        if not (config_entry := hass.config_entries.async_get_entry(entry_id)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_not_found",
                translation_placeholders={"target": DOMAIN},
            )
        if config_entry.state is not ConfigEntryState.LOADED:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_loaded",
                translation_placeholders={"target": config_entry.title},
            )
        panel = config_entry.runtime_data
        try:
            await panel.set_panel_date(value)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="incorrect_year"
            ) from err
        except asyncio.InvalidStateError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"target": config_entry.title},
            ) from err

    hass.services.async_register(
        DOMAIN,
        SET_DATE_TIME_SERVICE_NAME,
        async_set_panel_date,
        schema=SET_DATE_TIME_SCHEMA,
    )
