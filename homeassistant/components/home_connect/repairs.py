"""Repairs flows for Home Connect."""

from typing import cast

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant

from .coordinator import HomeConnectConfigEntry


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    assert issue_id.startswith("home_connect_too_many_connected_paired_events")
    assert data
    entry = hass.config_entries.async_get_entry(cast(str, data["entry_id"]))
    assert entry
    entry = cast(HomeConnectConfigEntry, entry)
    await entry.runtime_data.reset_execution_tracker(cast(str, data["appliance_ha_id"]))
    return ConfirmRepairFlow()
