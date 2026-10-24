"""Repairs for the Assist pipeline integration."""

import logging
from typing import Any, override

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

from .debug_recording import (
    DATA_DEBUG_RECORDINGS,
    ISSUE_LEFT_OVER,
    DebugRecordings,
    delete_debug_recordings,
)

_LOGGER = logging.getLogger(__name__)


class DebugRecordingsRepairFlow(ConfirmRepairFlow):
    """Delete the debug recordings after the user confirms."""

    def __init__(self, debug_recordings: DebugRecordings, issue_id: str) -> None:
        """Initialize the flow."""
        self._debug_recordings = debug_recordings
        self._issue_id = issue_id

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of the fix flow."""
        if user_input is None:
            return await super().async_step_confirm()

        debug_recordings = self._debug_recordings
        if self._issue_id == ISSUE_LEFT_OVER:
            recording_dirs = debug_recordings.left_over_dirs
            check = debug_recordings.async_check_left_over
        else:
            assert debug_recordings.recording_dir is not None
            recording_dirs = [debug_recordings.recording_dir]
            check = debug_recordings.async_check_still_enabled

        try:
            for recording_dir in recording_dirs:
                await self.hass.async_add_executor_job(
                    delete_debug_recordings, recording_dir
                )
        except OSError:
            _LOGGER.exception("Could not delete the debug recordings")
            return self.async_abort(reason="delete_failed")
        finally:
            # Also after a failure, as some recordings may be deleted already.
            await check()
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> DebugRecordingsRepairFlow:
    """Create a fix flow for the debug recording issues."""
    return DebugRecordingsRepairFlow(hass.data[DATA_DEBUG_RECORDINGS], issue_id)
