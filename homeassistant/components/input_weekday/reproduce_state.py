"""Reproduce an Input Weekday state."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, State

from . import ATTR_WEEKDAYS, DOMAIN, SERVICE_SET_WEEKDAYS

_LOGGER = logging.getLogger(__name__)


async def async_reproduce_states(
    hass: HomeAssistant,
    states: list[State],
    *,
    context: Context | None = None,
    reproduce_options: dict[str, Any] | None = None,
) -> None:
    """Reproduce Input Weekday states."""
    for state in states:
        if ATTR_WEEKDAYS not in state.attributes:
            _LOGGER.warning(
                "Unable to reproduce state for %s: %s attribute is missing",
                state.entity_id,
                ATTR_WEEKDAYS,
            )
            continue

        weekdays = state.attributes[ATTR_WEEKDAYS]

        service_data = {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_WEEKDAYS: weekdays,
        }

        await hass.services.async_call(
            DOMAIN, SERVICE_SET_WEEKDAYS, service_data, context=context, blocking=True
        )
