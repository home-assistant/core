"""iAlarmXR utils."""
import logging

from pyialarmxr import IAlarmXR

from homeassistant import core
from homeassistant.helpers.device_registry import format_mac

_LOGGER = logging.getLogger(__name__)


async def async_get_ialarmxr_mac(hass: core.HomeAssistant, ialarmxr: IAlarmXR) -> str:
    """Retrieve iAlarmXR MAC address."""
    _LOGGER.debug("Retrieving ialarmxr mac address")

    mac = await hass.async_add_executor_job(ialarmxr.get_mac)

    return format_mac(mac)
