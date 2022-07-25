"""Models for Repairs."""
from __future__ import annotations

from typing import Protocol

from homeassistant import data_entry_flow
from homeassistant.backports.enum import StrEnum
from homeassistant.core import HomeAssistant


class IssueSeverity(StrEnum):
    """Issue severity."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"


class RepairsFlow(data_entry_flow.FlowHandler):
    """Handle a flow for fixing an issue."""


class RepairsProtocol(Protocol):
    """Define the format of repairs platforms."""

    async def async_create_fix_flow(
        self, hass: HomeAssistant, issue_id: str
    ) -> RepairsFlow:
        """Create a flow to fix a fixable issue."""
