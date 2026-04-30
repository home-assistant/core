"""Test the CatGenie diagnostics."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from .conftest import MOCK_ENTRY_DATA

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test diagnostics output."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert "devices" in diagnostics
    assert len(diagnostics["devices"]) == 1
    assert diagnostics["devices"][0]["manufacturerId"] == "DEVICE001"
