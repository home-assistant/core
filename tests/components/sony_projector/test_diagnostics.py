"""Tests for Sony Projector diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration,
) -> None:
    """Test diagnostic information is returned and redacted."""

    diagnostics_info = AsyncMock(
        return_value={
            "user": "homeassistant",
            "installation_type": "Local",
        }
    )

    with (
        patch(
            "homeassistant.components.diagnostics.async_get_system_info",
            diagnostics_info,
        ),
        patch(
            "homeassistant.helpers.system_info.async_get_system_info",
            diagnostics_info,
        ),
    ):
        diag = await get_diagnostics_for_config_entry(
            hass, hass_client, init_integration
        )

    assert diag["host"] == REDACTED
    assert diag["serial"] == REDACTED
    assert "library_version" in diag
    assert diag["features"]["aspect_ratio"]
