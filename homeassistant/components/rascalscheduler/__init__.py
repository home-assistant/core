"""Support for rasc."""
from __future__ import annotations

import logging

from homeassistant.const import DOMAIN_RASCALSCHEDULER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .rascalscheduler import RascalSchedulerEntity

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN_RASCALSCHEDULER)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up RASCal scheduler."""
    _LOGGER.info("Setup rascal scheduler")
    hass.data[DOMAIN_RASCALSCHEDULER] = RascalSchedulerEntity()
    # hass.bus.async_listen(
    #     RASC_RESPONSE, hass.data[DOMAIN_RASCALSCHEDULER].event_listener
    # )
    return True
