"""The ping component."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from icmplib import SocketPermissionError, async_ping

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PING_COUNT, DOMAIN
from .coordinator import PingUpdateCoordinator
from .helpers import PingDataICMPLib, PingDataSubProcess

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER, Platform.SENSOR]


@dataclass(slots=True)
class PingDomainData:
    """Dataclass to store privileged status."""

    privileged: bool | None
    coordinators: dict[str, PingUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ping integration."""

    hass.data[DOMAIN] = PingDomainData(
        privileged=await _can_use_icmp_lib_with_privilege(),
        coordinators={},
    )

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
        hass=hass, ping=ping_cls(hass, host, count, data.privileged)
    )
    await coordinator.async_config_entry_first_refresh()

    data.coordinators[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # drop coordinator for config entry
        hass.data[DOMAIN].coordinators.pop(entry.entry_id)

    return unload_ok


async def _can_use_icmp_lib_with_privilege() -> bool | None:
    """Verify we can create a raw socket."""
    try:
        await async_ping("127.0.0.1", count=0, timeout=0, privileged=True)
    except SocketPermissionError:
        try:
            await async_ping("127.0.0.1", count=0, timeout=0, privileged=False)
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
