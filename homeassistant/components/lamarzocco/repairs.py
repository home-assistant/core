"""Repairs for La Marzocco."""

from typing import override

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant

from .const import CONF_OFFLINE_MODE, CONF_USE_BLUETOOTH


class DisableBluetoothRepairFlow(ConfirmRepairFlow):
    """Turn off Bluetooth for a machine without a Bluetooth token."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the flow."""
        self.entry_id = entry_id

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            if entry := self.hass.config_entries.async_get_entry(self.entry_id):
                # Offline mode requires Bluetooth
                self.hass.config_entries.async_update_entry(
                    entry,
                    options={
                        **entry.options,
                        CONF_USE_BLUETOOTH: False,
                        CONF_OFFLINE_MODE: False,
                    },
                )
                self.hass.config_entries.async_schedule_reload(self.entry_id)
            return self.async_create_entry(data={})
        return await super().async_step_confirm()


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    assert data is not None
    entry_id = data["entry_id"]
    assert isinstance(entry_id, str)
    return DisableBluetoothRepairFlow(entry_id)
