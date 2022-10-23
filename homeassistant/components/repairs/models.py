"""Models for Repairs."""
from __future__ import annotations

from typing import Protocol

from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant


class RepairsFlow(data_entry_flow.FlowHandler):
    """Handle a flow for fixing an issue."""

    issue_id: str
    data: dict[str, str | int | float | None] | None


class RepairsProtocol(Protocol):
    """Define the format of repairs platforms."""

    async def async_create_fix_flow(
        self,
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> RepairsFlow:
        """Create a flow to fix a fixable issue."""
