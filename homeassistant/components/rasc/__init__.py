"""The rasc integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    DOMAIN_RASCALRESCHEDULER,
    DOMAIN_RASCALSCHEDULER,
    JIT,
    RESCHEDULE_ALL,
    RESCHEDULING_ACCURACY,
    RESCHEDULING_ESTIMATION,
    RESCHEDULING_POLICY,
    RV,
    SCHEDULING_POLICY,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .abstraction import RASC
from .const import DOMAIN, LOGGER
from .rescheduler import RascalRescheduler
from .scheduler import RascalScheduler

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(SCHEDULING_POLICY, default=JIT): cv.string,
                vol.Optional(RESCHEDULING_POLICY, default=RV): cv.string,
                vol.Optional(RESCHEDULING_ESTIMATION, default=True): cv.boolean,
                vol.Optional(RESCHEDULING_ACCURACY, default=RESCHEDULE_ALL): cv.string,
                vol.Optional("mthresh", default=1): cv.positive_int,  # seconds
                vol.Optional("mithresh", default=2): cv.positive_int,  # seconds
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the RASC component."""
    component = hass.data[DOMAIN] = RASC(LOGGER, DOMAIN, hass)
    LOGGER.debug("RASC config: %s", config[DOMAIN])
    scheduler = hass.data[DOMAIN_RASCALSCHEDULER] = RascalScheduler(
        hass, config[DOMAIN]
    )
    rescheduler = hass.data[DOMAIN_RASCALRESCHEDULER] = RascalRescheduler(
        hass, scheduler.lineage_table, config[DOMAIN]
    )
    scheduler.reschedule_handler = rescheduler.handle_event

    await component.async_load()

    return True
