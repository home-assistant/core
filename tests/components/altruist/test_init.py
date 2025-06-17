"""Test the Altruist integration."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# @pytest.mark.parametrize(
#     "prepare_failure",
#     ["client_creation", "fetch_data"],
# )
# async def test_setup_entry_failures(
#     hass: HomeAssistant,
#     mock_config_entry: MockConfigEntry,
#     mock_altruist_client: AsyncMock,
#     prepare_failure: str,
# ) -> None:
#     """Test setup failure cases: client creation or data fetch."""

#     mock_config_entry.add_to_hass(hass)

#     if prepare_failure == "client_creation":
#         with patch(
#             "homeassistant.components.altruist.config_flow.AltruistClient.from_ip_address",
#             side_effect=Exception("Client creation failed"),
#         ):
#             result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

#     elif prepare_failure == "fetch_data":
#         mock_altruist_client.fetch_data.side_effect = Exception("Fetch failed")
#         result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

#     assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
#     assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_client_creation_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_altruist_client_fails_once: None,
) -> None:
    """Test setup failure when client creation fails."""
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_fetch_data_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_altruist_client: AsyncMock,
) -> None:
    """Test setup failure when initial data fetch fails."""
    mock_config_entry.add_to_hass(hass)
    mock_altruist_client.fetch_data.side_effect = Exception("Fetch failed")

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_altruist_client: AsyncMock,
) -> None:
    """Test unloading of config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Now test unloading
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
