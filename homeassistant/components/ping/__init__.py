"""The ping component."""
from __future__ import annotations

import logging

from icmplib import SocketPermissionError, ping as icmp_ping

from homeassistant.core import callback
from homeassistant.helpers.reload import async_setup_reload_service

from .const import DEFAULT_START_ID, DOMAIN, MAX_PING_ID, PING_ID, PING_PRIVS, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the template integration."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    hass.data[DOMAIN] = {
        PING_PRIVS: await hass.async_add_executor_job(_can_use_icmp_lib_with_privilege),
        PING_ID: DEFAULT_START_ID,
    }
    return True


@callback
def async_get_next_ping_id(hass, count=1):
    """Find the next id to use in the outbound ping.

    When using multiping, we increment the id
    by the number of ids that multiping
    will use.

    Must be called in async
    """
    allocated_id = hass.data[DOMAIN][PING_ID] + 1
    if allocated_id > MAX_PING_ID:
        allocated_id -= MAX_PING_ID - DEFAULT_START_ID
    hass.data[DOMAIN][PING_ID] += count
    if hass.data[DOMAIN][PING_ID] > MAX_PING_ID:
        hass.data[DOMAIN][PING_ID] -= MAX_PING_ID - DEFAULT_START_ID
    return allocated_id


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
