"""The Zeversolar integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.issue_registry import IssueSeverity

from .const import DOMAIN, PLATFORMS
from .coordinator import ZeversolarConfigEntry, ZeversolarCoordinator

_LOGGER = logging.getLogger(__name__)

_REPAIR_ISSUE_ID = "power_limit_api_unavailable"


async def async_setup_entry(hass: HomeAssistant, entry: ZeversolarConfigEntry) -> bool:
    """Set up Zeversolar from a config entry."""
    coordinator = ZeversolarCoordinator(hass=hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()

    # Probe after first refresh so we know the inverter is reachable before
    # attempting adv.cgi. The result gates switch/number/power-limit-sensor
    # availability for the lifetime of this config entry.
    coordinator.power_limit_supported = await coordinator.async_probe_power_limit_api()

    if coordinator.power_limit_supported:
        ir.async_delete_issue(hass, DOMAIN, _REPAIR_ISSUE_ID)
    else:
        ir.async_create_issue(
            hass,
            DOMAIN,
            _REPAIR_ISSUE_ID,
            is_fixable=False,
            is_persistent=False,
            severity=IssueSeverity.WARNING,
            translation_key=_REPAIR_ISSUE_ID,
        )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZeversolarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
