"""Tests for the weheat diagnostics."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.usefixtures("mock_weheat_discover", "mock_weheat_heat_pump")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.usefixtures("mock_weheat_discover")
async def test_diagnostics_without_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_weheat_heat_pump: AsyncMock,
) -> None:
    """Test the diagnostics of a heat pump that reported nothing yet."""
    mock_weheat_heat_pump.raw_content = None

    await setup_integration(hass, mock_config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["heat_pumps"][0]["logs"] == {}
    assert diagnostics["heat_pumps"][0]["energy"] == {}
