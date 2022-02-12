"""The ping component."""
from __future__ import annotations

import logging

from icmplib import SocketPermissionError, ping as icmp_ping

from homeassistant.core import HomeAssistant
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PING_PRIVS, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the template integration."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    hass.data[DOMAIN] = {
        PING_PRIVS: await hass.async_add_executor_job(_can_use_icmp_lib_with_privilege),
    }
    return True


def _can_use_icmp_lib_with_privilege() -> None | bool:
    """Verify we can create a raw socket."""
    try:
        icmp_ping("127.0.0.1", count=0, timeout=0, privileged=True)
    except SocketPermissionError:
        try:
            icmp_ping("127.0.0.1", count=0, timeout=0, privileged=False)
        except SocketPermissionError:
            _LOGGER.debug(
                "Cannot use icmplib because privileges are insufficient to create the socket"
            )
            return None
        else:
            _LOGGER.debug("Using icmplib in privileged=False mode")
            return False
    else:
        _LOGGER.debug("Using icmplib in privileged=True mode")
        return True
