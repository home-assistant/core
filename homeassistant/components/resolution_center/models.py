"""Models for Resolution Center."""
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


class ResolutionCenterFlow(data_entry_flow.FlowHandler):
    """Handle a flow for fixing an issue."""


class ResolutionCenterProtocol(Protocol):
    """Define the format of resolution center platforms."""

    async def async_create_fix_flow(
        self, hass: HomeAssistant, issue_id: str
    ) -> ResolutionCenterFlow:
        """Create a flow to fix a fixable issue."""
