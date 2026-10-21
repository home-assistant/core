"""Test SMLIGHT diagnostics."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry, async_load_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smlight.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import setup_integration


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    mock_smlight_client.get.return_value = await async_load_fixture(
        hass, "logs.txt", DOMAIN
    )
    entry = await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot
