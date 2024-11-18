"""Test SMLIGHT diagnostics."""

from unittest.mock import MagicMock

from syrupy import SnapshotAssertion

from homeassistant.components.smlight.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_smlight_client.get.return_value = load_fixture("logs.txt", DOMAIN)
    entry = await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot
