"""Models for Repairs."""

from __future__ import annotations

from typing import Protocol

from homeassistant.core import HomeAssistant

from . import issue_handler


class RepairsProtocol(Protocol):
    """Define the format of repairs platforms."""

    async def async_create_fix_flow(
        self,
        hass: HomeAssistant,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> issue_handler.RepairsFlow:
        """Create a flow to fix a fixable issue."""
