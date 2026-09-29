"""Repairs for the Assist pipeline integration."""

import logging
from pathlib import Path
from typing import Any, override

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

from .const import CONF_DEBUG_RECORDING_DIR, DATA_CONFIG
from .debug_recording import async_check_debug_recordings, delete_debug_recordings

_LOGGER = logging.getLogger(__name__)


class DebugRecordingsRepairFlow(ConfirmRepairFlow):
    """Delete the debug recordings after the user confirms."""

    def __init__(self, recording_dir: Path) -> None:
        """Initialize the flow."""
        self._recording_dir = recording_dir

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of the fix flow."""
        if user_input is None:
            return await super().async_step_confirm()

        try:
            await self.hass.async_add_executor_job(
                delete_debug_recordings, self._recording_dir
            )
        except OSError:
            _LOGGER.exception("Could not delete the debug recordings")
            # Some recordings may be deleted already.
            await async_check_debug_recordings(self.hass, self._recording_dir)
            return self.async_abort(reason="delete_failed")
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> DebugRecordingsRepairFlow:
    """Create a fix flow for the only fixable Assist pipeline issue."""
    # The issue is only created while a debug recording directory is configured.
    return DebugRecordingsRepairFlow(
        Path(hass.data[DATA_CONFIG][CONF_DEBUG_RECORDING_DIR])
    )
