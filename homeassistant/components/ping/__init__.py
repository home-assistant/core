"""The ping component."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from icmplib import SocketPermissionError, ping as icmp_ping
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PING_COUNT, DOMAIN
from .coordinator import PingUpdateCoordinator
from .ping import PingDataICMPLib, PingDataSubProcess

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(cv.deprecated(DOMAIN), cv.platform_only_config_schema(DOMAIN))
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]


@dataclass(slots=True)
class PingDomainData:
    """Dataclass to store coordinators and privileged status."""

    privileged: bool | None
    coordinators: dict[str, PingUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ping integration."""
    hass.data.setdefault(DOMAIN, {})

    data = PingDomainData(
        privileged=await hass.async_add_executor_job(_can_use_icmp_lib_with_privilege),
        coordinators={},
    )
    hass.data[DOMAIN] = data

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ping (ICMP) from a config entry."""

    data: PingDomainData = hass.data[DOMAIN]

    host: str = entry.options[CONF_HOST]
    count: int = int(entry.options[CONF_PING_COUNT])
    ping_cls: type[PingDataICMPLib | PingDataSubProcess]
    if data.privileged is None:
        ping_cls = PingDataSubProcess
    else:
        ping_cls = PingDataICMPLib

    coordinator = PingUpdateCoordinator(
        hass=hass, config_entry=entry, ping=ping_cls(hass, host, count, data.privileged)
    )
    await coordinator.async_config_entry_first_refresh()

    data.coordinators[entry.entry_id] = coordinator
    hass.data[DOMAIN] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # drop coordinator for config entry
        hass.data[DOMAIN].coordinators.pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _can_use_icmp_lib_with_privilege() -> None | bool:
    """Verify we can create a raw socket."""
    try:
        icmp_ping("127.0.0.1", count=0, timeout=0, privileged=True)
    except SocketPermissionError:
        try:
            icmp_ping("127.0.0.1", count=0, timeout=0, privileged=False)
        except SocketPermissionError:
            _LOGGER.debug(
                "Cannot use icmplib because privileges are insufficient to create the"
                " socket"
            )
            return None

        _LOGGER.debug("Using icmplib in privileged=False mode")
        return False

    _LOGGER.debug("Using icmplib in privileged=True mode")
    return True
