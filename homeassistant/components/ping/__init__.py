"""The ping component."""

from __future__ import annotations

import logging

from icmplib import SocketPermissionError, async_ping

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import CONF_PING_COUNT, DOMAIN
from .coordinator import PingConfigEntry, PingUpdateCoordinator
from .helpers import PingDataICMPLib, PingDataSubProcess

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER, Platform.SENSOR]
DATA_PRIVILEGED_KEY: HassKey[bool | None] = HassKey(DOMAIN)


async def async_migrate_entry(hass: HomeAssistant, entry: PingConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version == 1 and entry.minor_version == 1:
        _LOGGER.debug("Migrating to minor version 2")

        # Migrate device registry identifiers from homeassistant domain to ping domain
        registry = dr.async_get(hass)
        if (
            device := registry.async_get_device(
                identifiers={(HOMEASSISTANT_DOMAIN, entry.entry_id)}
            )
        ) is not None and entry.entry_id in device.config_entries:
            registry.async_update_device(
                device_id=device.id,
                new_identifiers={(DOMAIN, entry.entry_id)},
            )

        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ping integration."""
    hass.data[DATA_PRIVILEGED_KEY] = await _can_use_icmp_lib_with_privilege()

    return True


async def async_setup_entry(hass: HomeAssistant, entry: PingConfigEntry) -> bool:
    """Set up Ping (ICMP) from a config entry."""
    privileged = hass.data[DATA_PRIVILEGED_KEY]

    host: str = entry.options[CONF_HOST]
    count: int = int(entry.options[CONF_PING_COUNT])
    ping_cls: type[PingDataICMPLib | PingDataSubProcess]
    if privileged is None:
        ping_cls = PingDataSubProcess
    else:
        ping_cls = PingDataICMPLib

    coordinator = PingUpdateCoordinator(
        hass=hass, config_entry=entry, ping=ping_cls(hass, host, count, privileged)
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PingConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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
