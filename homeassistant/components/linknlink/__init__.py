"""The linknlink integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, get_domains
from .coordinator import Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a linknlink device from a config entry."""
    coordinator = Coordinator(hass, entry)
    if not await coordinator.async_setup():
        _LOGGER.error(
            "Unable to setup linknlink device - config=%s", coordinator.config.data
        )
        # 测试下能不能继续完成解锁TODO
        raise ConfigEntryNotReady

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    # Forward entry setup to related domains.
    await hass.config_entries.async_forward_entry_setups(
        entry, get_domains(coordinator.api.type)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device: Coordinator = hass.data[DOMAIN][entry.entry_id]
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, get_domains(device.api.type)
    )
    if unload_ok:
        device.unload()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
