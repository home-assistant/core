"""Repairs for the recorder."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.recorder import get_instance

from .const import DOMAIN, LOGGER
from .util import dburl_to_path, delete_corrupt_database_files


class CorruptDatabaseFilesRepairFlow(RepairsFlow):
    """Delete or keep the corrupt database files."""

    def __init__(self, names: list[str]) -> None:
        """Initialize the flow with the files the issue was created for."""
        self._names = names

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Offer to delete or keep the files."""
        description_placeholders = None
        if issue := ir.async_get(self.hass).async_get_issue(DOMAIN, self.issue_id):
            description_placeholders = issue.translation_placeholders
        return self.async_show_menu(
            step_id="init",
            menu_options=["delete", "keep"],
            description_placeholders=description_placeholders,
        )

    async def async_step_delete(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Delete the files."""
        try:
            await self.hass.async_add_executor_job(
                delete_corrupt_database_files,
                dburl_to_path(get_instance(self.hass).db_url),
                self._names,
            )
        except OSError:
            LOGGER.exception("Could not delete the corrupt database files")
            return self.async_abort(reason="delete_failed")
        return self.async_create_entry(data={})

    async def async_step_keep(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Keep the files and ignore the issue."""
        if ir.async_get(self.hass).async_get_issue(DOMAIN, self.issue_id):
            ir.async_ignore_issue(self.hass, DOMAIN, self.issue_id, True)
        return self.async_abort(reason="files_kept")


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> CorruptDatabaseFilesRepairFlow:
    """Create a fix flow for the only fixable recorder issue."""
    if TYPE_CHECKING:
        assert data is not None
    return CorruptDatabaseFilesRepairFlow(data["files"].split("/"))
