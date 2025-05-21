"""Services for the bosch_alarm integration."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import ATTR_CONFIG_ENTRY_ID, ATTR_DATETIME, DOMAIN, SERVICE_SET_DATE_TIME
from .types import BoschAlarmConfigEntry


def validate_datetime(value: Any) -> dt.datetime:
    """Validate that a provided datetime is supported on a bosch alarm panel."""
    date_val = cv.datetime(value)
    if date_val.year < 2010:
        raise vol.RangeInvalid("datetime must be after 2009")

    if date_val.year > 2037:
        raise vol.RangeInvalid("datetime must be before 2038")

    return date_val


SET_DATE_TIME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_DATETIME): validate_datetime,
    }
)


async def async_set_panel_date(call: ServiceCall) -> None:
    """Set the date and time on a bosch alarm panel."""
    config_entry: BoschAlarmConfigEntry | None
    value: dt.datetime = call.data.get(ATTR_DATETIME, dt_util.now())
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    if not (config_entry := call.hass.config_entries.async_get_entry(entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_not_found",
            translation_placeholders={"target": entry_id},
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
    except asyncio.InvalidStateError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={"target": config_entry.title},
        ) from err


def setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the bosch alarm integration."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DATE_TIME,
        async_set_panel_date,
        schema=SET_DATE_TIME_SCHEMA,
    )
