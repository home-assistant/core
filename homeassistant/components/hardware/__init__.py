"""The Hardware integration."""

from __future__ import annotations

import psutil_home_assistant as ha_psutil

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DATA_HARDWARE, DOMAIN
from .hardware import async_process_hardware_platforms
from .models import HardwareData, SystemStatus

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Hardware."""
    hass.data[DATA_HARDWARE] = HardwareData(
        hardware_platform={},
        system_status=SystemStatus(
            ha_psutil=await hass.async_add_executor_job(ha_psutil.PsutilWrapper),
            remove_periodic_timer=None,
            subscribers=set(),
        ),
    )
    await async_process_hardware_platforms(hass)

    await websocket_api.async_setup(hass)

    return True
