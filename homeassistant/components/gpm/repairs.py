"""Repairs for the GPM component."""

from typing import Any, cast

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


class RestartRequiredFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, data: dict[str, str | int | float | None] | None) -> None:  # noqa: D107
        super().__init__()
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
