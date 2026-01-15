"""Tests for the HDFury coordinator."""

from hdfury import HDFuryError
import pytest

from homeassistant.components.hdfury.coordinator import HDFuryCoordinator, HDFuryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_update_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hdfury_client,
) -> None:
    """Test successful coordinator update."""

    coordinator = HDFuryCoordinator(hass, mock_config_entry)

    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert isinstance(coordinator.data, HDFuryData)

    assert coordinator.data.board["hostname"] == "VRROOM-02"
    assert "portseltx0" in coordinator.data.info
    assert "autosw" in coordinator.data.config

    mock_hdfury_client.get_board.assert_awaited_once()
    mock_hdfury_client.get_info.assert_awaited_once()
    mock_hdfury_client.get_config.assert_awaited_once()


@pytest.mark.parametrize(
    "method",
    ["get_board", "get_info", "get_config"],
)
async def test_coordinator_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hdfury_client,
    method: str,
) -> None:
    """Test coordinator fails if any API call errors."""

    getattr(mock_hdfury_client, method).side_effect = HDFuryError()

    coordinator = HDFuryCoordinator(hass, mock_config_entry)

    with pytest.raises(
        UpdateFailed,
        match="communication_error",
    ):
        await coordinator._async_update_data()
