"""The Opower integration."""

from __future__ import annotations

from opower import select_utility

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .const import CONF_UTILITY, DOMAIN
from .coordinator import OpowerConfigEntry, OpowerCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OpowerConfigEntry) -> bool:
    """Set up Opower from a config entry."""
    utility_name = entry.data[CONF_UTILITY]
    try:
        select_utility(utility_name)
    except ValueError:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"unsupported_utility_{entry.entry_id}",
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="unsupported_utility",
            translation_placeholders={"utility": utility_name},
            data={
                "entry_id": entry.entry_id,
                "utility": utility_name,
                "title": entry.title,
            },
        )
        return False

    coordinator = OpowerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpowerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: OpowerConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    coordinator = entry.runtime_data
    active_device_ids = {
        f"{coordinator.api.utility.subdomain()}_{account_id}"
        for account_id in coordinator.data
    }

    # Do not allow removing devices that are still active in the API
    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN and identifier[1] in active_device_ids:
            return False

    return True
