"""Tests for the BSBLan coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bsblan import BSBLANConnectionError
import pytest

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.bsblan.coordinator import BSBLanUpdateCoordinator
from homeassistant.components.bsblan.models import BSBLanCoordinatorData
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_bsblan_client() -> MagicMock:
    """Create a mock BSBLAN client."""
    client = AsyncMock()
    client.state = AsyncMock()
    client.sensor = AsyncMock()
    return client


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Create a mock config entry."""
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Test BSB-Lan",
        data={CONF_HOST: "192.168.1.100"},
        source="test",
        options={},
        unique_id="unique_test_id",
    )


@pytest.mark.asyncio
async def test_coordinator_update(
    hass: HomeAssistant, mock_bsblan_client, mock_config_entry
) -> None:
    """Test the coordinator update method."""
    coordinator = BSBLanUpdateCoordinator(hass, mock_config_entry, mock_bsblan_client)

    # Mock the return values
    mock_state = MagicMock()
    mock_sensor = MagicMock()
    mock_bsblan_client.state.return_value = mock_state
    mock_bsblan_client.sensor.return_value = mock_sensor

    # Test successful update
    with patch.object(
        coordinator, "_get_update_interval", return_value=timedelta(seconds=30)
    ):
        data = await coordinator._async_update_data()

    assert isinstance(data, BSBLanCoordinatorData)
    assert data.state == mock_state
    assert data.sensor == mock_sensor
    assert coordinator.update_interval == timedelta(seconds=30)

    # Test failed update
    mock_bsblan_client.state.side_effect = BSBLANConnectionError("Connection failed")

    with (
        pytest.raises(UpdateFailed) as exc_info,
        patch.object(
            coordinator, "_get_update_interval", return_value=timedelta(seconds=30)
        ),
    ):
        await coordinator._async_update_data()

    assert (
        "Error while establishing connection with BSB-Lan device at 192.168.1.100"
        in str(exc_info.value)
    )
    assert coordinator.update_interval == timedelta(seconds=30)
