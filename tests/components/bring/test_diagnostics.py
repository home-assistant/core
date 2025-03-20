"""Test for diagnostics platform of the Bring! integration."""

from unittest.mock import AsyncMock

from bring_api import BringItemsResponse
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bring.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_bring_client")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    bring_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_bring_client: AsyncMock,
) -> None:
    """Test diagnostics."""
    mock_bring_client.get_list.side_effect = [
        BringItemsResponse.from_json(load_fixture("items.json", DOMAIN)),
        BringItemsResponse.from_json(load_fixture("items2.json", DOMAIN)),
    ]
    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, bring_config_entry)
        == snapshot
    )
