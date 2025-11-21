"""Test the Essent diagnostics."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

from . import setup_integration

pytestmark = pytest.mark.freeze_time("2025-11-16 12:00:00+01:00")


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock,
    essent_api_response: dict,
) -> None:
    """Test diagnostics for config entry."""
    entry = await setup_integration(hass, aioclient_mock, essent_api_response)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, entry
    )

    assert diagnostics["last_update_success"] is True
    assert diagnostics["coordinator_data"] is not None
    assert diagnostics["api_refresh_scheduled"] is False
    assert diagnostics["listener_tick_scheduled"] is False
    assert diagnostics["api_fetch_minute_offset"] == 5
    assert "electricity" in diagnostics["coordinator_data"]
    assert "gas" in diagnostics["coordinator_data"]
