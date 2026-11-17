"""ZHA repair for weekly schedule links that cannot be synced."""

from typing import Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from ..helpers import get_zha_data
from ..weekly_schedule import WeeklyScheduleRemovalError, WeeklyScheduleSyncManager


class WeeklyScheduleRepairFlow(RepairsFlow):
    """Let the user retry the sync or remove the link."""

    def __init__(self, link_id: str) -> None:
        """Initialize the flow."""
        self._link_id = link_id
        self._clear_error: str | None = None

    def _manager(self) -> WeeklyScheduleSyncManager | None:
        manager = get_zha_data(self.hass).weekly_schedule_sync
        if manager is None or not any(
            link["link_id"] == self._link_id for link in manager.async_links()
        ):
            return None
        return manager

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Offer the available fixes."""
        if self._manager() is None:
            return self.async_abort(reason="link_not_found")
        issue = ir.async_get(self.hass).async_get_issue(self.handler, self.issue_id)
        return self.async_show_menu(
            step_id="init",
            menu_options=["retry", "remove_link"],
            description_placeholders=issue.translation_placeholders if issue else None,
        )

    async def async_step_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Sync now and report the result."""
        if (manager := self._manager()) is None:
            return self.async_abort(reason="link_not_found")
        try:
            await manager.async_sync_now(self._link_id)
        except HomeAssistantError as err:
            return self.async_abort(
                reason="sync_failed", description_placeholders={"error": str(err)}
            )
        link = next(
            link for link in manager.async_links() if link["link_id"] == self._link_id
        )
        if link["state"] != "synced":
            return self.async_abort(
                reason="sync_failed",
                description_placeholders={"error": link["last_error"] or ""},
            )
        return self.async_create_entry(data={})

    async def async_step_remove_link(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Clear the thermostat schedule and remove the link."""
        if (manager := self._manager()) is None:
            return self.async_abort(reason="link_not_found")
        try:
            await manager.async_remove_link(self._link_id)
        except WeeklyScheduleRemovalError as err:
            self._clear_error = str(err)
            return await self.async_step_confirm_unlink()
        except HomeAssistantError as err:
            return self.async_abort(
                reason="clear_failed", description_placeholders={"error": str(err)}
            )
        return self.async_create_entry(data={})

    async def async_step_confirm_unlink(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Confirm unlinking without changing the thermostat."""
        if self._clear_error is None:
            return self.async_abort(
                reason="clear_failed",
                description_placeholders={"error": "No clear failure was reported"},
            )
        if (manager := self._manager()) is None:
            return self.async_abort(reason="link_not_found")
        if user_input is None:
            return self.async_show_form(
                step_id="confirm_unlink",
                description_placeholders={"error": self._clear_error},
            )
        try:
            await manager.async_remove_link(self._link_id, without_clearing=True)
        except HomeAssistantError as err:
            return self.async_abort(
                reason="clear_failed", description_placeholders={"error": str(err)}
            )
        return self.async_create_entry(data={})
