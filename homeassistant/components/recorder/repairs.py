"""Repairs for the recorder."""

import logging
from typing import Any, override

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

from .util import (
    CORRUPT_DATABASE_ISSUE_PREFIX,
    dburl_to_path,
    delete_corrupt_database_files,
    get_instance,
)

_LOGGER = logging.getLogger(__name__)


class CorruptDatabaseFilesRepairFlow(ConfirmRepairFlow):
    """Delete the corrupt database files after the user confirms."""

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of the fix flow."""
        if user_input is None:
            return await super().async_step_confirm()

        try:
            await self.hass.async_add_executor_job(
                delete_corrupt_database_files,
                dburl_to_path(get_instance(self.hass).db_url),
                self.issue_id.removeprefix(f"{CORRUPT_DATABASE_ISSUE_PREFIX}_"),
            )
        except OSError:
            _LOGGER.exception("Could not delete the corrupt database files")
            return self.async_abort(reason="delete_failed")
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> CorruptDatabaseFilesRepairFlow:
    """Create a fix flow for the only fixable recorder issue."""
    return CorruptDatabaseFilesRepairFlow()
