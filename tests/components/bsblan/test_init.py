"""Tests for the BSBLan integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from bsblan import BSBLANConnectionError
import pytest

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.bsblan.coordinator import BSBLanUpdateCoordinator
from homeassistant.components.bsblan.models import BSBLanCoordinatorData, BSBLanData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=BSBLanUpdateCoordinator)
    coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=BSBLANConnectionError
    )
    return coordinator


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the BSBLAN configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)

    # Mock the coordinator data
    mock_coordinator = MagicMock()
    mock_coordinator.data = BSBLanCoordinatorData(state=MagicMock(), sensor=MagicMock())

    # Create a mock BSBLanData instance
    mock_bsblan_data = BSBLanData(
        coordinator=mock_coordinator,
        client=mock_bsblan,
        device=MagicMock(),
        info=MagicMock(),
        static=MagicMock(),
    )

    with patch(
        "homeassistant.components.bsblan.BSBLanData", return_value=mock_bsblan_data
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_bsblan.device.mock_calls) == 1
    assert DOMAIN in hass.data and mock_config_entry.entry_id in hass.data[DOMAIN]

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Test the BSBLAN configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bsblan.BSBLanUpdateCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.bsblan.BSBLAN",
            return_value=mock_bsblan,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(mock_coordinator.async_config_entry_first_refresh.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.data.get(DOMAIN) is None
