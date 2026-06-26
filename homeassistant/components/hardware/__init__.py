"""The Hardware integration."""

import psutil_home_assistant as ha_psutil

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.integration_platform import LazyIntegrationPlatforms
from homeassistant.helpers.typing import ConfigType

from . import websocket_api
from .const import DATA_HARDWARE, DOMAIN
from .models import (
    BoardInfo,
    HardwareData,
    HardwareInfo,
    HardwareProtocol,
    SystemStatus,
    USBInfo,
)

__all__ = [
    "BoardInfo",
    "HardwareInfo",
    "USBInfo",
]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@callback
def _process_hardware_platform(
    hass: HomeAssistant, integration_domain: str, platform: HardwareProtocol
) -> HardwareProtocol:
    """Process a hardware platform."""
    return platform


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Hardware."""
    hass.data[DATA_HARDWARE] = HardwareData(
        hardware_platforms=LazyIntegrationPlatforms(
            hass, DOMAIN, _process_hardware_platform
        ),
        system_status=SystemStatus(
            ha_psutil=await hass.async_add_executor_job(ha_psutil.PsutilWrapper),
            remove_periodic_timer=None,
            subscribers=set(),
        ),
    )

    await websocket_api.async_setup(hass)

    return True
