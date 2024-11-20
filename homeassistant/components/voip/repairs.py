"""Repairs implementation for the VoIP integration."""

from __future__ import annotations

from homeassistant.components.assist_pipeline.repair_flows import (
    AssistInProgressDeprecatedRepairFlow,
)
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("assist_in_progress_deprecated"):
        return AssistInProgressDeprecatedRepairFlow(data)
    # If VoIP adds confirm-only repairs in the future, this should be changed
    # to return a ConfirmRepairFlow instead of raising a ValueError
    raise ValueError(f"unknown repair {issue_id}")
