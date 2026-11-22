"""Test the Fast.com component diagnostics."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import CoreState, HomeAssistant


async def test_get_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_async_fast_com: AsyncMock,
) -> None:
    """Test if get_config_entry_diagnostics returns redacted data."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert diagnostics == snapshot
    assert diagnostics["coordinator_data"]["client"]["ip"] == REDACTED
    assert diagnostics["coordinator_data"]["targets"][0]["url"] == REDACTED
    assert diagnostics["coordinator_data"]["targets"][0]["name"] == REDACTED


async def test_get_config_entry_diagnostics_no_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_async_fast_com: AsyncMock,
) -> None:
    """Test diagnostics when coordinator has no data yet."""
    mock_config_entry.add_to_hass(hass)

    original_state = hass.state
    hass.set_state(CoreState.starting)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    hass.set_state(original_state)

    mock_async_fast_com.assert_not_awaited()
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == {"coordinator_data": None}
