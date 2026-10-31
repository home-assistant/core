"""Test Litter-Robot diagnostics."""

from unittest.mock import MagicMock

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_diagnostics(
    hass: HomeAssistant,
    mock_account: MagicMock,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = await setup_integration(hass, mock_account)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert diag == snapshot
