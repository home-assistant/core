"""Tests for Tradfri diagnostics."""

from __future__ import annotations

import pytest
from pytradfri.device import Device

from homeassistant.core import HomeAssistant

from .common import setup_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize("device", ["air_purifier"], indirect=True)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device: Device,
) -> None:
    """Test diagnostics for config entry."""
    config_entry = await setup_integration(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(result, dict)
    assert result["gateway_version"] == "1.2.1234"
    assert result["device_data"] == ["STARKVIND Air purifier"]
