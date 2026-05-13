"""Test the Zeversolar coordinator."""

from unittest.mock import MagicMock

from zeversolar import ZeverSolarData
from zeversolar.exceptions import ZeverSolarError

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_update_success(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    zeversolar_data: ZeverSolarData,
) -> None:
    """Test coordinator fetches data successfully."""
    coordinator = init_integration.runtime_data

    assert coordinator.last_update_success is True
    assert coordinator.data == zeversolar_data


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_zeversolar_client: MagicMock,
) -> None:
    """Test coordinator marks update failed when client raises ZeverSolarError."""
    coordinator = init_integration.runtime_data

    mock_zeversolar_client.get_data.side_effect = ZeverSolarError
    await coordinator.async_refresh()
    mock_zeversolar_client.get_data.side_effect = None

    assert coordinator.last_update_success is False
