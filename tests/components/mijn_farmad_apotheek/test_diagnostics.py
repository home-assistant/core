"""Tests for the diagnostics data provided by the Mijn Farmad Apotheek integration."""

from unittest.mock import MagicMock

from aiofarmad import FarmadAuthenticationError
import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import init_integration

FIXED_MOCK_ENTRY_ID = "01JGFJJZ008DNE3BKJ7ZE14YFE"


@pytest.mark.freeze_time("2025-01-01T00:00:00+00:00")
@pytest.mark.usefixtures("mock_farmad_client")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a loaded entry."""
    entry = await init_integration(hass, entry_id=FIXED_MOCK_ENTRY_ID)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


@pytest.mark.freeze_time("2025-01-01T00:00:00+00:00")
async def test_diagnostics_failed_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_farmad_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for an entry whose setup failed."""
    mock_farmad_client.return_value.async_get_account.side_effect = (
        FarmadAuthenticationError("mock")
    )
    entry = await init_integration(hass, entry_id=FIXED_MOCK_ENTRY_ID)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
