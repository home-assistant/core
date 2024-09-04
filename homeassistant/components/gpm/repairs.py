"""Repairs for the GPM component."""

from collections.abc import Callable
from typing import Any, cast

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.issue_registry import IssueSeverity

from .const import DOMAIN


class RestartRequiredFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str | int | float | None] | None) -> None:  # noqa: D107
        self.data = data

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["restart"],
            description_placeholders=cast(dict[str, str], self.data),
        )

    async def async_step_restart(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the restart step of a fix flow."""
        await self.hass.services.async_call("homeassistant", "restart")
        return self.async_create_entry(title="", data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None = None,
    *args: Any,
    **kwargs: Any,
) -> RepairsFlow | None:
    """Create flow."""
    if issue_id.startswith("restart_required."):
        return RestartRequiredFixFlow(data)
    return None


def create_restart_issue(
    fn: Callable, hass: HomeAssistant, action: str, component_name: str
) -> None:
    """Create an issue to inform the user that a restart is required."""
    data: dict[str, str | int | float | None] = {
        "action": action,
        "name": component_name,
    }
    fn(
        hass=hass,
        domain=DOMAIN,
        issue_id=f"restart_required.{component_name}",
        is_fixable=True,
        issue_domain=component_name,
        severity=IssueSeverity.WARNING,
        translation_key="restart_required",
        translation_placeholders=data,
        data=data,
    )
