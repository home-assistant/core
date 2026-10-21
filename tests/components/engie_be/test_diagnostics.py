"""Test the diagnostics of the ENGIE Belgium integration."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from .conftest import setup_dynamic_entry, setup_entry


@pytest.mark.usefixtures("frozen_afternoon", "mock_engie_client")
async def test_diagnostics_fixed_tariff(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a household on a fixed tariff."""
    await setup_entry(hass, mock_config_entry)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))


@pytest.mark.usefixtures("frozen_afternoon")
async def test_diagnostics_dynamic_tariff(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a household on a dynamic tariff."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
